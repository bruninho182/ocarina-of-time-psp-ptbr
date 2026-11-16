"""Migra os diálogos Redux T1.8 para o port z2442, com validação dos arquivos."""
import argparse
import hashlib
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parent
CLEAN = "5bd1fe107bf8106b2ab6650abecd54d6"
REDUX = "49183ac38c714be6dcdd968db436b860"
JP_OFFSET, JP_SIZE = 0x8D72B0, 0x3A350
FONT_OFFSET, EN_OFFSET = 0x912800, 0x916D80
ASSET_BASE = 0x20000000
ASSET_PATH = Path("data/segments/oot_psp_assets.bin")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def rom_asset(rom, index, address):
    start, end, physical, compressed_end = struct.unpack_from(
        ">4I", rom, 0x7430 + 16 * index
    )
    require(start == address and end > start, "Entrada DMA inesperada.")
    size = end - start
    if not compressed_end:
        return rom[physical:physical + size]

    data = rom[physical:compressed_end]
    require(data[:8] == struct.pack(">4sI", b"Yaz0", size), "Cabeçalho Yaz0 inválido.")
    out = bytearray()
    cursor = 16
    while len(out) < size:
        flags = data[cursor]
        cursor += 1
        for bit in range(7, -1, -1):
            if len(out) == size:
                break
            if flags & (1 << bit):
                out.append(data[cursor])
                cursor += 1
                continue
            count, distance = divmod(int.from_bytes(data[cursor:cursor + 2], "big"), 4096)
            cursor += 2
            if count:
                count += 2
            else:
                count = data[cursor] + 18
                cursor += 1
            require(distance < len(out) and len(out) + count <= size, "Referência Yaz0 inválida.")
            for _ in range(count):
                out.append(out[-distance - 1])
    return bytes(out)


def load_rom(digest):
    for path in ROOT.glob("*/*.z64"):
        rom = path.read_bytes()
        if hashlib.md5(rom).hexdigest() == digest:
            return rom
    raise ValueError(f"ROM esperada não encontrada nas subpastas (MD5 {digest}).")


def resources(rom):
    bank = rom_asset(rom, 22, 0x92D000)
    font = rom_asset(rom, 21, 0x928000)
    code = rom_asset(rom, 27, 0xA87000)
    table = 0xF98AC + (2087 + 1) * 8
    rows = [
        struct.unpack_from(">HBxI", code, table + 8 * index)
        for index in range(2115)
    ]
    require(struct.unpack_from(">H", code, table + 2115 * 8)[0] == 0xFFFF,
            "Fim da tabela de diálogos inesperado.")
    require(len(font) == EN_OFFSET - FONT_OFFSET, "Tamanho da fonte inesperado.")
    psp_font = b"".join(font[i:i + 8][::-1] for i in range(0, len(font), 8))
    return bank, psp_font, rows


def psp_table(rows, bank, offset):
    pointers = [pointer - 0x07000000 for _, _, pointer in rows]
    ends = pointers[1:] + [len(bank)]
    base = ASSET_BASE + offset
    require(all(0 <= start <= end <= len(bank) for start, end in zip(pointers, ends)),
            "Ponteiro de diálogo fora do banco ou fora de ordem.")
    return b"".join(
        struct.pack("<HBBII", message_id, box, 0, base + start, base + end)
        for (message_id, box, _), start, end in zip(rows, pointers, ends)
    )


def patch(port, output, original, translated):
    clean_bank, clean_font, clean_rows = original
    bank, font, rows = translated
    eboot = bytearray((port / "EBOOT.PBP").read_bytes())
    assets = bytearray((port / ASSET_PATH).read_bytes())
    require(eboot[:4] == b"\x00PBP", "EBOOT.PBP inválido.")
    require(len(assets) == 0x3267B10, "Tamanho do pacote de recursos inesperado.")
    require(assets[EN_OFFSET:EN_OFFSET + len(clean_bank)] == clean_bank,
            "O banco inglês do port difere da ROM original.")
    require(assets[FONT_OFFSET:EN_OFFSET] == clean_font,
            "A fonte do port difere do formato esperado.")
    japanese = struct.pack("<6I", ASSET_BASE + JP_OFFSET, ASSET_BASE + JP_OFFSET + JP_SIZE,
                           0x8EB000, 0x925350, 0, JP_OFFSET)
    require(japanese in eboot, "O EBOOT não usa o layout esperado para o banco japonês.")
    old_table = psp_table(clean_rows, clean_bank, EN_OFFSET)
    signature = struct.pack("<I", len(clean_rows)) + old_table[:24]
    require(eboot.count(signature) == 1, "Tabela inglesa não localizada de forma única no EBOOT.")
    start = eboot.index(signature) + 4
    # Compare the IDs, box attributes and starting pointers against the clean ROM.
    # The port can use a different end pointer for the final entry.
    require(all(eboot[start + i:start + i + 8] == old_table[i:i + 8]
                for i in range(0, len(old_table), 12)),
            "A tabela inglesa do EBOOT difere da ROM original.")
    eboot[start:start + len(old_table)] = psp_table(rows, bank, JP_OFFSET)
    assets[JP_OFFSET:JP_OFFSET + len(bank)] = bank
    assets[FONT_OFFSET:EN_OFFSET] = font

    output.mkdir()
    (output / ASSET_PATH.parent).mkdir(parents=True)
    (output / "EBOOT.PBP").write_bytes(eboot)
    (output / ASSET_PATH).write_bytes(assets)
    print(f"Arquivos modificados gerados em {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port", type=Path, nargs="?", help="Pasta da instalação em inglês, após o primeiro boot")
    args = parser.parse_args()
    original = resources(load_rom(CLEAN))
    translated = resources(load_rom(REDUX))
    bank, _, rows = translated
    require([row[0] for row in original[2]] == [row[0] for row in rows],
            "Os IDs da tradução diferem dos IDs da ROM original.")
    require(len(bank) <= JP_SIZE, "O banco traduzido excede o espaço disponível.")
    psp_table(rows, bank, JP_OFFSET)
    print(f"ROMs verificadas: {len(rows)} entradas, {len(bank)} bytes de diálogos.")
    if args.port:
        patch(args.port, ROOT / "saida-ptbr", original, translated)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        raise SystemExit(f"Erro: {error}") from None
