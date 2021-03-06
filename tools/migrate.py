from mod import Music

from dotenv import load_dotenv
from git import Repo

import csv
import difflib
import logging
import os
from io import StringIO
from pathlib import Path

load_dotenv()
AUDIO_FORMAT = 'm4a'
DIFF_RANGE = 5
OUTPUT_DIR = Path(os.getenv('OUTPUT_DIR'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)s %(levelname)s - %(message)s',
)
console = logging.getLogger('migrate')


def get_filenames(header, lines):
    filelike = StringIO(header + "\n" + "\n".join(lines))
    musics = map(Music, csv.DictReader(filelike))
    return list(map(lambda x: [f'{x.video_type}:{x.video_id}@{x.clip_start}', x.hash], musics))


def pick_suisei_diff(diff, desc):
    csv_diff = list(filter(lambda x: x.a_path == 'suisei-music.csv', diff))
    if len(csv_diff) < 1:
        return None
    console.info(f'Picking diff for {desc}')
    return csv_diff[0]


def find_suisei_diff_on_log(repo):
    for i in range(1, DIFF_RANGE):
        name = f'HEAD~{i}'
        diff = pick_suisei_diff(repo.head.commit.diff(name), name)
        if diff is not None:
            return diff
    return None


def get_diff():
    csv_header = open('../suisei-music.csv',
                      encoding='utf-8').read().split('\n')[0]
    repo = Repo("../")
    diff = pick_suisei_diff(repo.index.diff(
        'HEAD'), 'staged') or find_suisei_diff_on_log(repo)
    if diff is None:
        console.error(
            'No staged/unstaged/HEAD~1 diff of suisei-music.csv found, exiting.')
        return
    console.debug('Diff found. Extracing...')
    new_data = diff.a_blob.data_stream.read().decode().split('\n')
    old_data = diff.b_blob.data_stream.read().decode().split('\n')
    smdiff = difflib.SequenceMatcher(None, old_data, new_data)
    lines_to_remove = []
    lines_to_add = []
    for op in smdiff.get_opcodes():
        if op[0] == 'equal':
            continue
        l = old_data[op[1]:op[2]]
        r = new_data[op[3]:op[4]]
        for j in l:
            lines_to_remove.append(j)
        for j in r:
            lines_to_add.append(j)
    entries_to_remove = get_filenames(csv_header, lines_to_remove)
    entries_to_add = get_filenames(csv_header, lines_to_add)
    final = {}
    for [identifier, filename] in entries_to_remove:
        final[identifier] = [filename, None]
    for [identifier, filename] in entries_to_add:
        if identifier in final:
            if final[identifier][0] == filename:
                del final[identifier]
            else:
                final[identifier] = [final[identifier][0], filename]
        else:
            final[identifier] = [None, filename]
    return final


def main():
    final = get_diff()
    for [key, [src, dst]] in final.items():
        if src is not None and dst is not None:
            source = f'{src}.{AUDIO_FORMAT}'
            destin = f'{dst}.{AUDIO_FORMAT}'
            print(f"Renaming {source} -> {destin} ({key})")
            if (OUTPUT_DIR / destin).exists():
                print(
                    f'{destin} is found, skipping. Please check if it is what you want.')
            elif not (OUTPUT_DIR / source).exists():
                print(f'{source} is not found, skipping.')
            else:
                os.rename(OUTPUT_DIR / source, OUTPUT_DIR / destin)


if __name__ == '__main__':
    main()
