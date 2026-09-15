"""Connect local ground copper islands to In1.Cu with checked through vias.

Run using the portable KiCad Python (with Shapely). This script preserves all
existing copper and uses explicit hole/copper clearances. Native KiCad DRC is
still required. These signal-ground connections do not size power returns.
"""
import argparse
import json
import math
from pathlib import Path
import pcbnew as pcb
from shapely.geometry import Point, Polygon, LineString, box
from shapely.ops import unary_union
from shapely.prepared import prep
from preconnect import octilinear_paths

MM = pcb.FromMM
COPPER = [pcb.F_Cu, pcb.In1_Cu, pcb.In2_Cu, pcb.B_Cu]


def xy(p):
    return pcb.ToMM(p.x), pcb.ToMM(p.y)


def polyset(shape):
    polygons = []
    for i in range(shape.OutlineCount()):
        outline = shape.Outline(i)
        coords = [xy(outline.CPoint(j)) for j in range(outline.PointCount())]
        if len(coords) >= 3:
            polygons.append(Polygon(coords).buffer(0))
    return unary_union(polygons)


def copper_shape(pad, layer):
    return polyset(pad.GetEffectivePolygon(layer))


def hole_shape(pad):
    poly = pcb.SHAPE_POLY_SET()
    pad.TransformHoleToPolygon(poly, 0, MM(0.0005), pcb.ERROR_OUTSIDE)
    return polyset(poly)


def track_shape(track):
    if isinstance(track, pcb.PCB_VIA):
        return Point(xy(track.GetPosition())).buffer(pcb.ToMM(track.GetWidth(pcb.F_Cu)) / 2, quad_segs=24)
    if isinstance(track, pcb.PCB_ARC):
        raise ValueError('Arc input is not yet supported; refusing incomplete obstacles')
    return LineString([xy(track.GetStart()), xy(track.GetEnd())]).buffer(pcb.ToMM(track.GetWidth()) / 2, quad_segs=12)


def connect_ground(board, radius_limit=1.4):
    net = board.FindNet('GND')
    if not net:
        raise ValueError('GND net absent')
    if board.GetCopperLayerCount() != 4:
        raise ValueError('This geometry implementation expects four copper layers')
    if not any(z.GetNetname() == 'GND' and z.GetLayer() == pcb.In1_Cu for z in board.Zones()):
        raise ValueError('A continuous In1.Cu ground zone is required')
    pads = list(board.GetPads())
    layers = (pcb.F_Cu, pcb.B_Cu)
    other = {layer: [] for layer in COPPER}
    ground = {layer: [] for layer in layers}
    ground_pads = {layer: [] for layer in layers}
    connected_holes = []
    drill_obstacles = []
    # Avoid drilling into any component's solderable land; through vias are
    # ordinary tented dogbones, not an unqualified via-in-pad process.
    smd_lands = []
    for pad in pads:
        is_gnd = pad.GetNetname() == 'GND'
        for layer in COPPER:
            if not pad.IsOnLayer(layer):
                continue
            shape = copper_shape(pad, layer)
            if shape.is_empty:
                continue
            if not is_gnd:
                other[layer].append(shape.buffer(0.101))
            if layer in layers and is_gnd:
                ground[layer].append(shape)
                ground_pads[layer].append((pad, shape))
            if layer in layers and pad.GetAttribute() == pcb.PAD_ATTRIB_SMD:
                smd_lands.append(shape)
        if pad.HasHole():
            h = hole_shape(pad)
            if h.is_empty:
                continue
            clearance = 0.301 if pad.GetAttribute() == pcb.PAD_ATTRIB_PTH else 0.201
            # Via-to-component-hole spacing is 0.20 mm; this also excludes
            # same-net mechanical interference with the component hole.
            drill_obstacles.append(h.buffer(0.201 + 0.1))
            if not is_gnd:
                for layer in COPPER:
                    other[layer].append(h.buffer(clearance))
            elif pad.GetAttribute() == pcb.PAD_ATTRIB_PTH:
                connected_holes.append(Point(xy(pad.GetPosition())))
    for track in board.GetTracks():
        shape = track_shape(track)
        active = COPPER if isinstance(track, pcb.PCB_VIA) else [track.GetLayer()]
        if track.GetNetname() == 'GND':
            for layer in layers:
                if layer in active:
                    ground[layer].append(shape)
            if isinstance(track, pcb.PCB_VIA):
                connected_holes.append(Point(xy(track.GetPosition())))
        else:
            for layer in active:
                if layer in other:
                    other[layer].append(shape.buffer(0.101))
            if isinstance(track, pcb.PCB_VIA):
                drill = Point(xy(track.GetPosition())).buffer(pcb.ToMM(track.GetDrill()) / 2)
                for layer in COPPER:
                    other[layer].append(drill.buffer(0.201))
                drill_obstacles.append(drill.buffer(0.201 + 0.1))
    other_shapes = {layer: unary_union(shapes) for layer, shapes in other.items()}
    trace_width, via_diameter, via_drill = 0.2, 0.45, 0.2
    trace_blocked = {layer: prep(shape.buffer(trace_width / 2 + 0.001)) for layer, shape in other_shapes.items()}
    via_blocked = prep(unary_union(list(other_shapes.values())).buffer(via_diameter / 2 + 0.001)
                       .union(unary_union(smd_lands).buffer(via_drill / 2 + 0.051))
                       .union(unary_union(drill_obstacles)))
    outline = board.GetBoardEdgesBoundingBox()
    x0, y0 = xy(outline.GetPosition())
    x1, y1 = x0 + pcb.ToMM(outline.GetWidth()), y0 + pcb.ToMM(outline.GetHeight())
    # Edge bbox includes the 0.05-mm outline stroke; reserve its half width.
    allowed = box(x0 + 0.331 + via_diameter / 2, y0 + 0.331 + via_diameter / 2,
                  x1 - 0.331 - via_diameter / 2, y1 - 0.331 - via_diameter / 2)
    added, skipped, unresolved = [], [], []
    for layer in layers:
        union = unary_union(ground[layer])
        islands = list(union.geoms) if union.geom_type == 'MultiPolygon' else [union]
        # Process the largest islands first, letting a later small island use
        # the same via when a short legal trace reaches it.
        islands.sort(key=lambda s: -s.area)
        for island in islands:
            members = [(pad, shape) for pad, shape in ground_pads[layer] if island.intersects(shape)]
            if not members:
                continue
            refs = [f'{p.GetParentFootprint().GetReference()}.{p.GetNumber()}' for p, _ in members]
            if any(island.intersects(h) for h in connected_holes):
                skipped.append(refs)
                continue
            choices = []
            for pad, shape in members:
                pos = xy(pad.GetPosition())
                for endpoint in connected_holes:
                    target = endpoint.x, endpoint.y
                    length = math.dist(pos, target)
                    if length <= radius_limit:
                        for path in octilinear_paths(pos,target):
                            if not trace_blocked[layer].intersects(LineString(path)):
                                choices.append((0, length, pos, target, False, path))
                for radius in (0.4, 0.55, 0.7, 0.9, 1.1, 1.4):
                    if radius > radius_limit:
                        continue
                    for angle in range(0, 360, 45):
                        a = math.radians(angle)
                        target = tuple(round(v, 6) for v in (pos[0] + radius * math.cos(a), pos[1] + radius * math.sin(a)))
                        point = Point(target)
                        if not allowed.contains(point) or via_blocked.intersects(point):
                            continue
                        # Avoid overlapping independently added ground via holes.
                        if any(point.distance(h) < via_drill + 0.201 for h in connected_holes):
                            continue
                        if trace_blocked[layer].intersects(LineString([pos, target])):
                            continue
                        choices.append((1, radius, pos, target, True, [pos,target]))
            if not choices:
                unresolved.append(refs)
                continue
            _, length, start, end, new_via, path = min(choices)
            for seg_start,seg_end in zip(path,path[1:]):
                track = pcb.PCB_TRACK(board)
                track.SetStart(pcb.VECTOR2I(MM(seg_start[0]), MM(seg_start[1])))
                track.SetEnd(pcb.VECTOR2I(MM(seg_end[0]), MM(seg_end[1])))
                track.SetWidth(MM(trace_width)); track.SetLayer(layer); track.SetNet(net)
                board.Add(track)
            if new_via:
                via = pcb.PCB_VIA(board)
                via.SetPosition(track.GetEnd()); via.SetWidth(MM(via_diameter)); via.SetDrill(MM(via_drill))
                via.SetViaType(pcb.VIATYPE_THROUGH); via.SetLayerPair(pcb.F_Cu, pcb.B_Cu); via.SetNet(net)
                board.Add(via)
                connected_holes.append(Point(end))
            added.append(dict(refs=refs, layer=board.GetLayerName(layer), start=start, end=end,
                              length_mm=length, new_via=new_via))
    board.BuildConnectivity()
    pcb.ZONE_FILLER(board).Fill(board.Zones())
    return dict(added=added, existing_plane_connected_islands=skipped, unresolved_islands=unresolved,
                vias_added=sum(x['new_via'] for x in added), trace_count=len(added),
                limitations=['Signal ground fanout only; power/thermal returns require separate sizing.',
                             'Run native KiCad DRC before routing the remaining signals.'])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('board', type=Path)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--report', type=Path, required=True)
    args = ap.parse_args()
    if args.board.resolve() == args.out.resolve():
        raise ValueError('Output must be a separate board file')
    board = pcb.LoadBoard(str(args.board))
    report = connect_ground(board)
    pcb.SaveBoard(str(args.out), board)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('vias_added', 'trace_count', 'unresolved_islands')}, indent=2))


if __name__ == '__main__':
    main()
