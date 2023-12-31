import sys
sys.path.insert(0, '..') # ugly ass hack :/

import json

from glob import glob
from typing import List

from fsc.flipper_format.base import FlipperFormat
from fsc.flipper_format.infrared import read_ir

####################################################################################################

DB_FILES = "Flipper-IRDB-official/**/*.ir"
SILENT_MODE = True
CONFIDENCE = 0.8

####################################################################################################

class IRDBFile:
    def __init__(self, path) -> None:
        self.path = path
        self.hashes = {}
        self.count = 0

    def load(self):
        # load signal hashes
        with FlipperFormat(self.path) as fff:
            signals = read_ir(fff)
            for signal in signals:
                self.count += 1
                h = hash(signal)
                if h not in self.hashes:
                    self.hashes[h] = []
                self.hashes[h].append(signal.name)

def check(db: List[IRDBFile], path: str) -> list:
    # parse signals in current file
    with FlipperFormat(path) as fff:
        signals = [z for z in read_ir(fff)]
    signals_len = len(signals)
    
    result = []
    for data in db:
        # ignore self
        if data.path == path:
            continue

        common, input_only, checked_only = {}, {}, {}
        common_count, input_count, checked_count = 0, 0, 0

        """
        common   [both]: { hash -> [POWER OFF, [POWER ON]] }
        left [checking]: { hash -> FANS ON }
        right [checked]: { hash -> FANS OFF }
        """
        for input_signal in signals:
            input_signal_hash = hash(input_signal)
            if input_signal_hash in data.hashes:
                # both files have the same signal
                common[input_signal_hash] = [input_signal.name, data.hashes[input_signal_hash]]
                common_count += 1
            else:
                # the input file has a signal more
                input_only[input_signal_hash] = input_signal.name
                input_count += 1
        for checked_signal_hash, checked_signal_name in data.hashes.items():
            if not checked_signal_hash in common:
                # the checked file has a signal more
                checked_only[checked_signal_hash] = checked_signal_name
                checked_count += 1
        
        # confidence from 0.0 to 1.0 that the checking signals match the file
        # even if the checked file contains less signals, the confidence can be 1.0.
        common_confidence = common_count / max(1, data.count)

        # percentage how many new signals from input file to checked file
        # if the input file contains 4 signals and the checked file only contains 3,
        # the checking_balance would be 0.25 if the other 3 signals matche
        input_balance = input_count / max(1, data.count)

        # percentage how many new signals from checked file to checking file
        # see above.
        checked_balance = checked_count / signals_len

        # confidence from 0.0 to 1.0 that both the checking file and checked file 
        # have the same amounts of signals
        balance_confidence = min(data.count, signals_len) / max(data.count, signals_len)

        if common_confidence >= CONFIDENCE and balance_confidence >= CONFIDENCE:
            result.append({
                "path": data.path,
                "confidence": common_confidence,
                "balance": {
                    "confidence": balance_confidence,
                    "adds": checked_count,
                    "addsp": round(checked_balance * 100),
                    "misses": input_count,
                    "missesp": round(input_balance * 100),
                },
                "common": {cn[0]: cn[1] for _, cn in common.items()}
            })
    return result

def create_database() -> List[IRDBFile]:
    res = []
    for ir in glob(DB_FILES, recursive=True):
        if not SILENT_MODE: print("[DB] Loading", ir)
        irdb = IRDBFile(ir)
        irdb.load()
        res.append(irdb)
    return res

if __name__ == "__main__":
    if not SILENT_MODE: print("[db] Reading database ...")
    db = create_database()
    if not SILENT_MODE: 
        print("  [db] done!")
        print()

    input_files = []
    for arg in sys.argv[1:]:
        if arg.startswith("glob:"):
            input_files.extend(glob(arg[5:], recursive=True))
        elif arg.startswith("file:"):
            with open(arg[5:], "r") as fd:
                input_files.extend([z.strip() for z in fd.readlines()])
        else:
            input_files.append(arg)

    fat = {}
    for file in input_files:
        fat[file] = check(db, file)
    print(json.dumps(fat, indent=4))
