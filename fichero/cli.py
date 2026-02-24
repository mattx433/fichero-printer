"""CLI for Fichero D11s thermal label printer."""

import argparse
import asyncio
import os
import sys

from PIL import Image

from fichero.imaging import image_to_raster, prepare_image, text_to_image
from fichero.printer import (
    BYTES_PER_ROW,
    DELAY_AFTER_DENSITY,
    DELAY_AFTER_FEED,
    DELAY_COMMAND_GAP,
    DELAY_RASTER_SETTLE,
    PAPER_GAP,
    PrinterClient,
    PrinterError,
    PrinterNotReady,
    connect,
)


async def do_print(
    pc: PrinterClient,
    img: Image.Image,
    density: int = 1,
    paper: int = PAPER_GAP,
    copies: int = 1,
) -> bool:
    img = prepare_image(img)
    rows = img.height
    raster = image_to_raster(img)

    print(f"  Image: {img.width}x{rows}, {len(raster)} bytes, {copies} copies")

    status = await pc.get_status()
    if not status.ok:
        raise PrinterNotReady(f"Printer not ready: {status}")

    await pc.set_density(density)
    await asyncio.sleep(DELAY_AFTER_DENSITY)

    for copy_num in range(copies):
        if copies > 1:
            print(f"  Copy {copy_num + 1}/{copies}...")

        # AiYin print sequence (from decompiled APK)
        await pc.set_paper_type(paper)
        await asyncio.sleep(DELAY_COMMAND_GAP)
        await pc.wakeup()
        await asyncio.sleep(DELAY_COMMAND_GAP)
        await pc.enable()
        await asyncio.sleep(DELAY_COMMAND_GAP)

        # Raster image: GS v 0 m xL xH yL yH <data>
        yl = rows & 0xFF
        yh = (rows >> 8) & 0xFF
        header = bytes([0x1D, 0x76, 0x30, 0x00, BYTES_PER_ROW, 0x00, yl, yh])
        await pc.send_chunked(header + raster)

        await asyncio.sleep(DELAY_RASTER_SETTLE)
        await pc.form_feed()
        await asyncio.sleep(DELAY_AFTER_FEED)

        ok = await pc.stop_print()
        if not ok:
            print("  WARNING: no OK/0xAA from stop command")

    return True


async def cmd_info(args: argparse.Namespace) -> None:
    async with connect(args.address) as pc:
        info = await pc.get_info()
        for k, v in info.items():
            print(f"  {k}: {v}")

        print()
        all_info = await pc.get_all_info()
        for k, v in all_info.items():
            print(f"  {k}: {v}")


async def cmd_status(args: argparse.Namespace) -> None:
    async with connect(args.address) as pc:
        status = await pc.get_status()
        print(f"  Status: {status}")
        print(f"  Raw: 0x{status.raw:02X} ({status.raw:08b})")
        print(f"  printing={status.printing} cover_open={status.cover_open} "
              f"no_paper={status.no_paper} low_battery={status.low_battery} "
              f"overheated={status.overheated} charging={status.charging}")


async def cmd_text(args: argparse.Namespace) -> None:
    text = " ".join(args.text)
    img = text_to_image(text, font_size=args.font_size, label_height=args.label_height)
    async with connect(args.address) as pc:
        print(f'Printing "{text}"...')
        ok = await do_print(pc, img, args.density, copies=args.copies)
        print("Done." if ok else "FAILED.")


async def cmd_image(args: argparse.Namespace) -> None:
    img = Image.open(args.path)
    async with connect(args.address) as pc:
        print(f"Printing {args.path}...")
        ok = await do_print(pc, img, args.density, copies=args.copies)
        print("Done." if ok else "FAILED.")


async def cmd_set(args: argparse.Namespace) -> None:
    async with connect(args.address) as pc:
        if args.setting == "density":
            val = int(args.value)
            if not 0 <= val <= 2:
                print("  ERROR: density must be 0, 1, or 2")
                return
            ok = await pc.set_density(val)
            print(f"  Set density={args.value}: {'OK' if ok else 'FAILED'}")
        elif args.setting == "shutdown":
            val = int(args.value)
            if not 1 <= val <= 480:
                print("  ERROR: shutdown must be 1-480 minutes")
                return
            ok = await pc.set_shutdown_time(val)
            print(f"  Set shutdown={args.value}min: {'OK' if ok else 'FAILED'}")
        elif args.setting == "paper":
            types = {"gap": 0, "black": 1, "continuous": 2}
            if args.value in types:
                val = types[args.value]
            else:
                try:
                    val = int(args.value)
                except ValueError:
                    print("  ERROR: paper must be gap, black, continuous, or 0-2")
                    return
                if not 0 <= val <= 2:
                    print("  ERROR: paper must be gap, black, continuous, or 0-2")
                    return
            ok = await pc.set_paper_type(val)
            print(f"  Set paper={args.value}: {'OK' if ok else 'FAILED'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fichero D11s Label Printer")
    parser.add_argument("--address", default=os.environ.get("FICHERO_ADDR"),
                        help="BLE address (skip scanning, or set FICHERO_ADDR)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_info = sub.add_parser("info", help="Show device info")
    p_info.set_defaults(func=cmd_info)

    p_status = sub.add_parser("status", help="Show detailed status")
    p_status.set_defaults(func=cmd_status)

    p_text = sub.add_parser("text", help="Print text label")
    p_text.add_argument("text", nargs="+", help="Text to print")
    p_text.add_argument("--density", type=int, default=1, choices=[0, 1, 2],
                        help="Print density: 0=light, 1=medium, 2=thick")
    p_text.add_argument("--copies", type=int, default=1, help="Number of copies")
    p_text.add_argument("--font-size", type=int, default=24, help="Font size in points")
    p_text.add_argument("--label-height", type=int, default=240,
                        help="Label height in pixels (default: 240)")
    p_text.set_defaults(func=cmd_text)

    p_image = sub.add_parser("image", help="Print image file")
    p_image.add_argument("path", help="Path to image file")
    p_image.add_argument("--density", type=int, default=1, choices=[0, 1, 2],
                         help="Print density: 0=light, 1=medium, 2=thick")
    p_image.add_argument("--copies", type=int, default=1, help="Number of copies")
    p_image.set_defaults(func=cmd_image)

    p_set = sub.add_parser("set", help="Change printer settings")
    p_set.add_argument("setting", choices=["density", "shutdown", "paper"],
                       help="Setting to change")
    p_set.add_argument("value", help="New value")
    p_set.set_defaults(func=cmd_set)

    args = parser.parse_args()
    try:
        asyncio.run(args.func(args))
    except PrinterError as e:
        print(f"  ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
