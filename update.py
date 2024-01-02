import itertools
import json
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Tuple, Union
from datetime import datetime

SIGNAL_UUID = os.environ.get("SIGNAL_UUID")
SIGNAL_PASSWORD = os.environ.get("SIGNAL_PASSWORD")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_USERID = os.environ.get("TELEGRAM_USERID")

StickerPacksUrlType = Dict[str, Dict[str, Union[Dict[str, List[str]], str]]]
LimojiSortedDictType = Dict[str, Dict[str, Any]]
ExportTypesType = Tuple[str, ...]
FmtsType = Tuple[str, ...]
RegenPackType = List[Tuple[str, ExportTypesType, FmtsType]]

DEFAULT_EXPORT_TYPES: ExportTypesType = ("signal", "telegram", "whatsapp")
DEFAULT_FMTS: FmtsType = ("gif", "png")


def update_icons():
    os.system("git submodule foreach git pull origin main")


def get_regen_packs(
    data_old: LimojiSortedDictType,
    data_new: LimojiSortedDictType,
) -> RegenPackType:
    regen_packs: RegenPackType = []

    for pack_new, v_new in data_new.items():
        icons_new = set(
            [i[1] for i in v_new.get("icons", [])]
            + [i[1] for i in v_new.get("special", [])]
        )

        if pack_new not in os.listdir("sticker_packs"):
            regen_packs.append((pack_new, DEFAULT_EXPORT_TYPES, DEFAULT_FMTS))
            continue

        v_old = data_old.get(pack_new)
        if v_old is None:
            regen_packs.append((pack_new, DEFAULT_EXPORT_TYPES, DEFAULT_FMTS))
            continue

        icons_old = set(
            [i[1] for i in v_old.get("icons", [])]
            + [i[1] for i in v_old.get("special", [])]
        )

        if pack_new not in set(data_old.keys()):
            regen_packs.append((pack_new, DEFAULT_EXPORT_TYPES, DEFAULT_FMTS))
            continue

        if icons_old != icons_new:
            regen_packs.append((pack_new, DEFAULT_EXPORT_TYPES, DEFAULT_FMTS))

    return regen_packs


def generate_packs(
    data: LimojiSortedDictType,
    sticker_packs_url: StickerPacksUrlType,
    pack: str,
    export_types: ExportTypesType = DEFAULT_EXPORT_TYPES,
    fmts: FmtsType = DEFAULT_FMTS,
):
    sticker_paths = data[pack].get("icons", [])
    sticker_paths += data[pack].get("special", [])

    for export_type, fmt in itertools.product(export_types, fmts):
        result = generate_pack(sticker_paths, pack, export_type, fmt)
        if not sticker_packs_url.get(pack):
            sticker_packs_url[pack] = {}
        if not sticker_packs_url[pack].get(export_type):
            sticker_packs_url[pack][export_type] = {}
        sticker_packs_url[pack][export_type][fmt] = result  # type: ignore
    sticker_packs_url[pack]["update"] = datetime.today().strftime("%Y-%m-%d")


def generate_pack(
    sticker_paths: List[str], pack: str, export_type: str, fmt: str
) -> List[str]:
    if fmt == "gif":
        pack_name = "LIHKG_" + pack
        idx = 1
    else:
        pack_name = "LIHKG_" + pack + "_static"
        idx = 2

    output_dir = f"sticker_packs/{pack}/{export_type}/{fmt}"
    print(f"Generating {output_dir}")

    shutil.rmtree(output_dir, ignore_errors=True)
    os.makedirs(output_dir)

    with tempfile.TemporaryDirectory() as input_dir_temp:
        # This is to retain the order of icons in sticker pack
        for count, sticker_path in enumerate(sticker_paths):
            sticker_ext = os.path.splitext(sticker_path[idx])[-1]
            f_src = os.path.join("lihkg-icons", f"{sticker_path[idx]}")
            f_dst = os.path.join(input_dir_temp, f"{str(count).zfill(3)}{sticker_ext}")
            if os.path.exists(f_src):
                shutil.copy(f_src, f_dst)
            else:
                print(f"Warning: {f_src} does not exist")

        cmd = [
            "sticker-convert",
            "--custom-presets",
            "custom_preset.json",
            f"--input-dir",
            os.path.abspath(input_dir_temp),
            f"--output-dir",
            os.path.abspath(output_dir),
            "--author",
            "LIHKG_unofficial",
            f"--title",
            pack_name,
            f"--export-{export_type}",
            "--no-confirm",
        ]

        if pack == "mf":
            if export_type == "whatsapp":
                cmd.append("--fps-min")
                cmd.append("8")
                cmd.append("--fps-power")
                cmd.append("-1")
                cmd.append("--duration-max")
                cmd.append("3000")
            elif export_type == "telegram":
                cmd.append("--fps-min")
                cmd.append("4")
                cmd.append("--fps-power")
                cmd.append("-1")
                cmd.append("--duration-max")
                cmd.append("2000")

        if SIGNAL_UUID:
            cmd.append(f"--signal-uuid")
            cmd.append(SIGNAL_UUID)
        else:
            print("WARNING: SIGNAL_UUID not set")

        if SIGNAL_PASSWORD:
            cmd.append(f"--signal-password")
            cmd.append(SIGNAL_PASSWORD)
        else:
            print("WARNING: SIGNAL_PASSWORD not set")

        if TELEGRAM_TOKEN:
            cmd.append(f"--telegram-token")
            cmd.append(TELEGRAM_TOKEN)
        else:
            print("WARNING: TELEGRAM_TOKEN not set")

        if TELEGRAM_USERID:
            cmd.append(f"--telegram-userid")
            cmd.append(TELEGRAM_USERID)
        else:
            print("WARNING: TELEGRAM_USERID not set")

        if fmt == "gif":
            cmd.append("--fake-vid")

        subprocess.run(cmd, check=True)

    if export_type != "whatsapp":
        with open(f"{output_dir}/export-result.txt") as f:
            return f.read().strip().split("\n")
    else:
        os.remove(f"{output_dir}/export-result.txt")
        wastickers_urls: List[str] = []
        for f in os.listdir(output_dir):
            if os.path.splitext(f)[1] == ".wastickers":
                url = f"./{output_dir}/{f}?raw=1"
                wastickers_urls.append(url)
        return wastickers_urls


def update_readme(data: LimojiSortedDictType, sticker_packs_url: StickerPacksUrlType):
    with open("README_TEMPLATE") as f:
        readme = f.read()

    with open("lihkg-icons/jsons/mapping.json") as f:
        mapping: Dict[str, str] = json.load(f)

    body = "| Code | Name | Preview | Date | WhatsApp | Signal | Telegram |\n"
    body += "| --- | --- | --- | --- | --- | --- | --- |\n"

    for pack, v1 in sticker_packs_url.items():
        pack_zh = mapping.get(pack, pack)

        pack_paths = [i[1] for i in data.get(pack, {}).get("icons", [])]
        pack_paths += [i[1] for i in data.get(pack, {}).get("special", [])]

        preview_path = (
            "https://raw.githubusercontent.com/laggykiller/lihkg-icons/main/"
            + pack_paths[0]
        )
        preview_name = os.path.split(preview_path)[-1]

        link_strs = {}
        for export_type, v2 in v1.items():
            if export_type == "update":
                continue

            link_strs[export_type] = ""

            assert not isinstance(v2, str)
            for fmt, links in v2.items():
                if fmt == "png":
                    pack_name = pack + "_static"
                else:
                    pack_name = pack

                for count, link in enumerate(links):
                    link_strs[export_type] += f"[{pack_name}_{count}]({link})<br>"

        body += f"| {pack} | {pack_zh} | ![{preview_name}]({preview_path}) | {v1.get('update')} | {link_strs['whatsapp']} | {link_strs['signal']} | {link_strs['telegram']} |\n"

    readme = readme.replace("{body}", body)

    with open("README.md", "w+") as f:
        f.write(readme)


def main():
    regen = not os.path.isdir("sticker_packs")
    if regen:
        print("sticker_packs directory missing, regenerating all packs")
        os.mkdir("sticker_packs")
        data_old: LimojiSortedDictType = {}
        sticker_packs_url: StickerPacksUrlType = {}
    else:
        with open("lihkg-icons/jsons/limoji_sorted.json") as f:
            data_old = json.load(f)

        if os.path.isfile("sticker_packs_url.json"):
            with open("sticker_packs_url.json") as f:
                sticker_packs_url = json.load(f)
        else:
            sticker_packs_url = {}

    update_icons()

    with open("lihkg-icons/jsons/limoji_sorted.json") as f:
        data_new = json.load(f)

    regen_packs: RegenPackType = []
    for i in sys.argv[1:]:
        item_info = i.split("-")
        pack = item_info[0]
        export_type = item_info[1] if len(item_info) >= 2 else "*"
        fmt = item_info[2] if len(item_info) >= 3 else "*"

        if export_type == "*":
            export_types = DEFAULT_EXPORT_TYPES
        elif export_type not in DEFAULT_EXPORT_TYPES:
            print(f"Invalid export type {export_type}. Accepts: {DEFAULT_EXPORT_TYPES}")
            return
        else:
            export_types = (export_type,)

        if fmt == "*":
            fmts = DEFAULT_FMTS
        elif fmt not in DEFAULT_FMTS:
            print(f"Invalid format {fmt}. Accepts: {DEFAULT_FMTS}")
            return
        else:
            fmts = (fmt,)

        if pack == "*":
            for i in data_new:
                regen_packs.append((i, export_types, fmts))
        else:
            regen_packs.append((pack, export_types, fmts))

    regen_packs.extend(get_regen_packs(data_old, data_new))

    for pack, export_types, fmts in regen_packs:
        generate_packs(data_new, sticker_packs_url, pack, export_types, fmts)

        with open("sticker_packs_url.json", "w+") as f:
            json.dump(sticker_packs_url, f, indent=4)

    update_readme(data_new, sticker_packs_url)


if __name__ == "__main__":
    main()
