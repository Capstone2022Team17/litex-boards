import argparse

parser = argparse.ArgumentParser(
                    prog = 'hbm_bist_test.py',
                    description = 'Performs AXI reads and writes to verify performance of high-bandwidth memory IP cores',
                    epilog = 'Defaults to burst mode increasing with a bank offset of 0')

parser.add_argument('-s' , '--single', action="store_true", help="Switches to single write mode, ignores burst argument")
parser.add_argument('-m', '--burstmode', action='store', choices=["INCR", "FIXED", "WRAP"], default="INCR", help="Switches AXI burst mode")
parser.add_argument('-o', '--bank_offset', action='store', type=int, help="Changes offset between memory banks, reduces bank conflicts")

parser.parse_args()