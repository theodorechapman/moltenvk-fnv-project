#!/usr/bin/env python3
"""Analyze D3D9 trace files captured by the replay recorder."""

import struct
import sys
import os
from pathlib import Path

# Constants from d3d9_trace_format.h
D3D9_TRACE_MAGIC = 0x4543415254394433  # "D3D9TRAC"

# Draw call types
DRAW_TYPES = {
    0: "DrawPrimitive",
    1: "DrawIndexedPrimitive",
    2: "DrawPrimitiveUP",
    3: "DrawIndexedPrimitiveUP",
}

# Primitive types
PRIM_TYPES = {
    1: "PointList",
    2: "LineList",
    3: "LineStrip",
    4: "TriangleList",
    5: "TriangleStrip",
    6: "TriangleFan",
}

def calc_vertex_count(prim_type, prim_count):
    """Calculate vertex count from primitive type and count."""
    if prim_type == 1:    # PointList
        return prim_count
    elif prim_type == 2:  # LineList
        return prim_count * 2
    elif prim_type == 3:  # LineStrip
        return prim_count + 1
    elif prim_type == 4:  # TriangleList
        return prim_count * 3
    elif prim_type == 5:  # TriangleStrip
        return prim_count + 2
    elif prim_type == 6:  # TriangleFan
        return prim_count + 2
    return 0

# Resource types (matches D3D9TraceResourceType enum)
RESOURCE_TYPES = {
    0: "Texture2D",
    1: "TextureCube",
    2: "Texture3D",
    3: "VertexBuffer",
    4: "IndexBuffer",
    5: "VertexShader",
    6: "PixelShader",
    7: "VertexDecl",
}

def read_header(f):
    """Read and parse trace header (accounting for struct padding)."""
    # C struct has padding between uint32_t backbufferHeight and uint64_t stateOffset
    # Layout: Q(8) + 7I(28) + 4-byte padding + 6Q(48) = 88 bytes
    header_fmt = "<Q7I4x6Q"
    header_size = struct.calcsize(header_fmt)
    data = f.read(header_size)
    if len(data) < header_size:
        return None

    values = struct.unpack(header_fmt, data)
    return {
        'magic': values[0],
        'version': values[1],
        'flags': values[2],
        'frameNumber': values[3],
        'drawCallCount': values[4],
        'resourceCount': values[5],
        'backbufferWidth': values[6],
        'backbufferHeight': values[7],
        'stateOffset': values[8],
        'drawCallsOffset': values[9],
        'resourcesOffset': values[10],
        'resourceDataOffset': values[11],
        'referenceFrameOffset': values[12],
        'totalSize': values[13],
    }

def read_draw_call(f):
    """Read a single draw call record (variable size based on type)."""
    # Base header: type(u8), primitiveType(u8), hasStateDelta(u8), reserved(u8), primitiveCount(u32)
    base_fmt = "<4BI"
    base_size = struct.calcsize(base_fmt)
    data = f.read(base_size)
    if len(data) < base_size:
        return None

    base = struct.unpack(base_fmt, data)
    draw_type = base[0]

    draw = {
        'type': draw_type,
        'primitiveType': base[1],
        'hasStateDelta': base[2],
        'primitiveCount': base[4],
        'startVertex': 0,
        'vertexCount': 0,
        'baseVertexIndex': 0,
        'minVertexIndex': 0,
        'numVertices': 0,
        'startIndex': 0,
    }

    if draw_type == 0:  # DrawPrimitive
        # startVertex (u32)
        extra = f.read(4)
        if len(extra) >= 4:
            draw['startVertex'] = struct.unpack("<I", extra)[0]
    elif draw_type == 1:  # DrawIndexedPrimitive
        # baseVertexIndex(i32), minVertexIndex(u32), numVertices(u32), startIndex(u32)
        extra = f.read(16)
        if len(extra) >= 16:
            vals = struct.unpack("<iIII", extra)
            draw['baseVertexIndex'] = vals[0]
            draw['minVertexIndex'] = vals[1]
            draw['numVertices'] = vals[2]
            draw['startIndex'] = vals[3]
    elif draw_type == 2:  # DrawPrimitiveUP
        # vertexStride(u32), vertexDataSize(u32), then vertex data
        extra = f.read(8)
        if len(extra) >= 8:
            vals = struct.unpack("<II", extra)
            draw['vertexStride'] = vals[0]
            draw['vertexDataSize'] = vals[1]
            if vals[1] > 0:
                f.read(vals[1])  # Skip inline vertex data
    elif draw_type == 3:  # DrawIndexedPrimitiveUP
        # minVertexIndex(u32), numVertices(u32), vertexStride(u32), indexFormat(u32),
        # vertexDataSize(u32), indexDataSize(u32), then data
        extra = f.read(24)
        if len(extra) >= 24:
            vals = struct.unpack("<6I", extra)
            draw['minVertexIndex'] = vals[0]
            draw['numVertices'] = vals[1]
            draw['vertexStride'] = vals[2]
            draw['indexFormat'] = vals[3]
            draw['vertexDataSize'] = vals[4]
            draw['indexDataSize'] = vals[5]
            # Skip inline data
            if vals[4] > 0:
                f.read(vals[4])
            if vals[5] > 0:
                f.read(vals[5])

    return draw

def read_resource_entry(f):
    """Read a resource table entry (56 bytes total due to struct padding)."""
    # Layout: id(4) + type(1) + reserved(3) + dataOffset(8) + dataSize(8) + union(28) + padding(4) = 56
    entry_size = 56
    data = f.read(entry_size)
    if len(data) < entry_size:
        return None

    # Parse fixed header
    id_val = struct.unpack('<I', data[0:4])[0]
    type_val = data[4]  # single byte
    data_offset = struct.unpack('<Q', data[8:16])[0]
    data_size = struct.unpack('<Q', data[16:24])[0]

    entry = {
        'id': id_val,
        'type': type_val,
        'dataOffset': data_offset,
        'dataSize': data_size,
    }

    # Parse type-specific union data (starts at byte 24)
    union_data = data[24:56]
    if type_val == 0:  # Texture2D
        vals = struct.unpack('<6I', union_data[:24])
        entry['width'] = vals[0]
        entry['height'] = vals[1]
        entry['mipLevels'] = vals[2]
        entry['format'] = vals[3]
    elif type_val == 3:  # VertexBuffer
        vals = struct.unpack('<4I', union_data[:16])
        entry['size'] = vals[0]
        entry['usage'] = vals[1]
        entry['fvf'] = vals[2]
        entry['pool'] = vals[3]
    elif type_val == 4:  # IndexBuffer
        vals = struct.unpack('<4I', union_data[:16])
        entry['size'] = vals[0]
        entry['usage'] = vals[1]
        entry['format'] = vals[2]
        entry['pool'] = vals[3]
    elif type_val in (5, 6):  # Shaders
        entry['bytecodeSize'] = struct.unpack('<I', union_data[:4])[0]
    elif type_val == 7:  # VertexDecl
        entry['elementCount'] = struct.unpack('<I', union_data[:4])[0]

    return entry

def analyze_trace(filepath):
    """Analyze a single trace file."""
    print(f"\n{'='*60}")
    print(f"Analyzing: {filepath.name}")
    print(f"{'='*60}")

    file_size = os.path.getsize(filepath)
    print(f"File size: {file_size:,} bytes ({file_size/1024:.1f} KB)")

    with open(filepath, 'rb') as f:
        header = read_header(f)
        if not header:
            print("ERROR: Failed to read header")
            return None

        if header['magic'] != D3D9_TRACE_MAGIC:
            print(f"ERROR: Invalid magic: {header['magic']:016x}")
            return None

        print(f"\nHeader:")
        print(f"  Frame: {header['frameNumber']}")
        print(f"  Draw calls: {header['drawCallCount']}")
        print(f"  Resources: {header['resourceCount']}")
        print(f"  Backbuffer: {header['backbufferWidth']}x{header['backbufferHeight']}")

        result = {'header': header, 'draws': [], 'resources': []}

        # Analyze draw calls
        if header['drawCallCount'] > 0 and header['drawCallsOffset'] > 0:
            f.seek(header['drawCallsOffset'])

            draw_type_counts = {}
            prim_type_counts = {}
            total_primitives = 0
            total_vertices = 0

            for i in range(min(header['drawCallCount'], 10000)):
                draw = read_draw_call(f)
                if not draw:
                    break

                result['draws'].append(draw)
                dtype = DRAW_TYPES.get(draw['type'], f"Unknown({draw['type']})")
                ptype = PRIM_TYPES.get(draw['primitiveType'], f"Unknown({draw['primitiveType']})")

                draw_type_counts[dtype] = draw_type_counts.get(dtype, 0) + 1
                prim_type_counts[ptype] = prim_type_counts.get(ptype, 0) + 1
                total_primitives += draw['primitiveCount']
                # Calculate vertex count from primitive count and type
                verts = calc_vertex_count(draw['primitiveType'], draw['primitiveCount'])
                total_vertices += verts

            print(f"\nDraw Call Analysis:")
            print(f"  Total primitives: {total_primitives:,}")
            print(f"  Total vertices: {total_vertices:,}")
            print(f"  Avg prims/draw: {total_primitives/max(1,header['drawCallCount']):.1f}")
            print(f"  Draw types:")
            for dtype, count in sorted(draw_type_counts.items(), key=lambda x: -x[1]):
                pct = 100*count/header['drawCallCount']
                print(f"    {dtype}: {count} ({pct:.1f}%)")
            print(f"  Primitive types:")
            for ptype, count in sorted(prim_type_counts.items(), key=lambda x: -x[1]):
                pct = 100*count/header['drawCallCount']
                print(f"    {ptype}: {count} ({pct:.1f}%)")

            result['total_primitives'] = total_primitives
            result['total_vertices'] = total_vertices
            result['draw_type_counts'] = draw_type_counts

        # Analyze resources
        if header['resourceCount'] > 0 and header['resourcesOffset'] > 0:
            f.seek(header['resourcesOffset'])

            resource_type_counts = {}
            total_resource_data = 0

            for i in range(header['resourceCount']):
                res = read_resource_entry(f)
                if not res:
                    break

                result['resources'].append(res)
                rtype = RESOURCE_TYPES.get(res['type'], f"Unknown({res['type']})")
                resource_type_counts[rtype] = resource_type_counts.get(rtype, 0) + 1
                total_resource_data += res['dataSize']

            print(f"\nResource Analysis:")
            print(f"  Total resource data: {total_resource_data:,} bytes ({total_resource_data/1024/1024:.2f} MB)")
            print(f"  Resource types:")
            for rtype, count in sorted(resource_type_counts.items(), key=lambda x: -x[1]):
                print(f"    {rtype}: {count}")

            result['resource_type_counts'] = resource_type_counts
            result['total_resource_data'] = total_resource_data

        return result

def main():
    traces_dir = Path("traces")
    if not traces_dir.exists():
        print("No traces directory found")
        return

    trace_files = sorted(traces_dir.glob("*.d3d9trace"))
    if not trace_files:
        print("No trace files found")
        return

    print(f"Found {len(trace_files)} trace files")

    results = []
    for trace_file in trace_files:
        result = analyze_trace(trace_file)
        if result:
            results.append((trace_file, result))

    # Summary comparison
    print(f"\n{'='*60}")
    print("SUMMARY - Batching Opportunity Analysis")
    print(f"{'='*60}")
    print(f"{'Frame':>8} {'Draws':>6} {'Prims':>8} {'Verts':>8} {'P/D':>6} {'Resources':>10}")
    print("-"*60)
    for trace_file, result in results:
        h = result['header']
        prims = result.get('total_primitives', 0)
        verts = result.get('total_vertices', 0)
        ppd = prims / max(1, h['drawCallCount'])
        print(f"{h['frameNumber']:>8} {h['drawCallCount']:>6} {prims:>8} {verts:>8} {ppd:>6.1f} {h['resourceCount']:>10}")

    # Batching analysis
    print(f"\n{'='*60}")
    print("BATCHING POTENTIAL")
    print(f"{'='*60}")
    if results:
        avg_draws = sum(r['header']['drawCallCount'] for _, r in results) / len(results)
        avg_prims_per_draw = sum(r.get('total_primitives',0) for _, r in results) / sum(r['header']['drawCallCount'] for _, r in results)
        
        print(f"Average draws per frame: {avg_draws:.0f}")
        print(f"Average primitives per draw: {avg_prims_per_draw:.1f}")
        
        if avg_prims_per_draw < 100:
            print(f"\n⚠️  LOW PRIMITIVES PER DRAW ({avg_prims_per_draw:.1f})")
            print("   This indicates many small draw calls - HIGH batching potential!")
            print("   Batching similar draws could significantly reduce CPU overhead.")
        
        # Check for DrawPrimitiveUP usage
        total_up = 0
        total_draws = 0
        for _, result in results:
            dtc = result.get('draw_type_counts', {})
            total_up += dtc.get('DrawPrimitiveUP', 0) + dtc.get('DrawIndexedPrimitiveUP', 0)
            total_draws += result['header']['drawCallCount']
        
        if total_up > 0:
            up_pct = 100 * total_up / total_draws
            print(f"\n⚠️  USER POINTER DRAWS: {total_up} ({up_pct:.1f}%)")
            print("   DrawPrimitiveUP/DrawIndexedPrimitiveUP require data upload each call.")
            print("   These are expensive and harder to batch.")

if __name__ == "__main__":
    main()
