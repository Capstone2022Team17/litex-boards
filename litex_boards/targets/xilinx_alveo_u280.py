#!/usr/bin/env python3

#
# This file is part of LiteX-Boards.
#
# Copyright (c) 2021 Sergiu Mosanu <sm7ed@virginia.edu>
# Copyright (c) 2020-2021 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2020 Antmicro <www.antmicro.com>
#
# SPDX-License-Identifier: BSD-2-Clause

# To interface via the serial port use:
#     lxterm /dev/ttyUSBx --speed=115200

from email.policy import default
import os
from litex.soc.interconnect.axi import axi_lite

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.gen import LiteXModule

from litex_boards.platforms import xilinx_alveo_u280

from litex.soc.cores.clock import *
from litex.soc.integration.soc_core import *
from litex.soc.integration.soc import SoCRegion
from litex.soc.integration.builder import *
from litex.soc.interconnect.axi import *
from litex.soc.interconnect.csr import *
from litex.soc.cores.ram.xilinx_usp_hbm2 import USPHBM2

from litex.soc.cores.led import LedChaser
from litedram.modules import MTA18ASF2G72PZ
from litedram.phy import usddrphy

from litepcie.phy.usppciephy import USPPCIEPHY
from litepcie.software import generate_litepcie_software

from litedram.common import *
from litedram.frontend.axi import *

from litescope import LiteScopeAnalyzer

from litedram.frontend.bist import  LiteDRAMBISTGenerator, LiteDRAMBISTChecker

from litex_boards.targets.HBMPortAccess import HBMReadAndWriteSM, HBMCSRSCommon #, HBMBISTStarter, HBMBIST

from litex.build.sim.config import SimConfig

# CRG ----------------------------------------------------------------------------------------------

class _CRG(LiteXModule):
    def __init__(self, platform, sys_clk_freq, ddram_channel, with_hbm):
        if with_hbm:
            self.cd_sys     = ClockDomain()
            self.cd_hbm_ref = ClockDomain()
            self.cd_apb     = ClockDomain()
        else: # ddr4
            self.rst = Signal()
            self.cd_sys    = ClockDomain()
            self.cd_sys4x  = ClockDomain()
            self.cd_pll4x  = ClockDomain()
            self.cd_idelay = ClockDomain()

            #############################
            self.cd_hbm_ref = ClockDomain()
            self.cd_apb     = ClockDomain()
            self.cd_axi_ref = ClockDomain()
            #############################

        # # #

        if with_hbm:
            self.pll = pll = USMMCM(speedgrade=-2)
            pll.register_clkin(platform.request("sysclk", ddram_channel), 100e6)
            pll.create_clkout(self.cd_sys,     sys_clk_freq)
            pll.create_clkout(self.cd_hbm_ref, 100e6)
            pll.create_clkout(self.cd_apb,     100e6)
            platform.add_false_path_constraints(self.cd_sys.clk, self.cd_apb.clk)
        else: # ddr4
            self.pll = pll = USMMCM(speedgrade=-2)
            self.comb += pll.reset.eq(self.rst)
            pll.register_clkin(platform.request("sysclk", ddram_channel), 100e6)

            ##########################################
            pll.create_clkout(self.cd_hbm_ref, 100e6)
            pll.create_clkout(self.cd_apb,     100e6)
            # pll.create_clkout(self.cd_axi_ref, 400e6)
            ##########################################

            pll.create_clkout(self.cd_pll4x, sys_clk_freq*4, buf=None, with_reset=False)
            pll.create_clkout(self.cd_idelay, 600e6) #, with_reset=False
            platform.add_false_path_constraints(self.cd_sys.clk, pll.clkin) # Ignore sys_clk to pll.clkin path created by SoC's rst.

            self.specials += [
                Instance("BUFGCE_DIV",
                    p_BUFGCE_DIVIDE=4,
                    i_CE=1, i_I=self.cd_pll4x.clk, o_O=self.cd_sys.clk),
                Instance("BUFGCE",
                    i_CE=1, i_I=self.cd_pll4x.clk, o_O=self.cd_sys4x.clk),
                # AsyncResetSynchronizer(self.cd_idelay, ~pll.locked),
            ]

            self.idelayctrl = USIDELAYCTRL(cd_ref=self.cd_idelay, cd_sys=self.cd_sys)

# BaseSoC ------------------------------------------------------------------------------------------

class BaseSoC(SoCCore):
    # csr_peripherals += "analyzer"
    # csr_map_update(BaseSoC.csr_map, csr_peripherals)

    def __init__(self, sys_clk_freq=150e6, ddram_channel=0,
        with_pcie       = False,
        with_led_chaser = False,
        with_hbm        = False,
        **kwargs):
        platform = xilinx_alveo_u280.Platform()
        if with_hbm:
            assert 225e6 <= sys_clk_freq <= 450e6





        # CRG --------------------------------------------------------------------------------------
        self.crg = _CRG(platform, sys_clk_freq, ddram_channel, with_hbm)

        # SoCCore ----------------------------------------------------------------------------------
        SoCCore.__init__(self, platform, sys_clk_freq, ident="LiteX SoC on Alveo U280 (ES1)", **kwargs)

        # HBM / DRAM -------------------------------------------------------------------------------
        if with_hbm:
            # JTAGBone -----------------------------------------------------------------------------
            #self.add_jtagbone(chain=2) # Chain 1 already used by HBM2 debug probes.

            # Add HBM Core.
            self.hbm = hbm = ClockDomainsRenamer({"axi": "sys"})(USPHBM2(platform))

            # Get HBM .xci.
            os.system("wget https://github.com/litex-hub/litex-boards/files/6893157/hbm_0.xci.txt")
            os.makedirs("ip/hbm", exist_ok=True)
            os.system("mv hbm_0.xci.txt ip/hbm/hbm_0.xci")

            # Connect four of the HBM's AXI interfaces to the main bus of the SoC.
            for i in range(4):
                axi_hbm      = hbm.axi[i]
                axi_lite_hbm = AXILiteInterface(data_width=256, address_width=33)
                self.submodules += AXILite2AXI(axi_lite_hbm, axi_hbm)
                self.bus.add_slave(f"hbm{i}", axi_lite_hbm, SoCRegion(origin=0x4000_0000 + 0x1000_0000*i, size=0x1000_0000)) # 256MB.
            # Link HBM2 channel 0 as main RAM
            self.bus.add_region("main_ram", SoCRegion(origin=0x4000_0000, size=0x1000_0000, linker=True)) # 256MB.

            #####################################################################################
            # Added code 

            # axi_lite_hbm = AXILiteInterface(data_width=256, address_width=33)
            # self.submodules += AXILite2AXI(axi_lite_hbm, hbm.axi[4])

            for i in range(4, 32):
                setattr(self.submodules, f"hbm_{i}", HBMReadAndWriteSM(hbm.axi[i]))
                # self.submodules.hbm_4 = HBMReadAndWriteSM(hbm.axi[i])
                self.add_csr(f"hbm_{i}")

            #####################################################################################
        
        else:
            # DDR4 SDRAM -------------------------------------------------------------------------------
            if not self.integrated_main_ram_size:
                self.ddrphy = usddrphy.USPDDRPHY(platform.request("ddram", ddram_channel),
                    memtype          = "DDR4",
                    cmd_latency      = 1, # seems to work better with cmd_latency=1
                    sys_clk_freq     = sys_clk_freq,
                    iodelay_clk_freq = 600e6,
                    is_rdimm         = True)
                self.add_sdram("sdram",
                    phy           = self.ddrphy,
                    module        = MTA18ASF2G72PZ(sys_clk_freq, "1:4"),
                    size          = 0x40000000,
                    l2_cache_size = kwargs.get("l2_size", 8192)
                )

            # Firmware RAM (To ease initial LiteDRAM calibration support) --------------------------
            self.add_ram("firmware_ram", 0x20000000, 0x8000)

            # Add HBM Core.
            self.hbm = hbm = ClockDomainsRenamer({"axi": "sys"})(USPHBM2(platform))

            # Get HBM .xci.
            os.system("wget https://github.com/litex-hub/litex-boards/files/6893157/hbm_0.xci.txt")
            os.makedirs("ip/hbm", exist_ok=True)
            os.system("mv hbm_0.xci.txt ip/hbm/hbm_0.xci")

            #####################################################################################
            # Added code 

            self.submodules.commonRegs = HBMCSRSCommon()

            for i in range(0, 32):
                setattr(self.submodules, f"hbm_{i}", HBMReadAndWriteSM(hbm.axi[i], self.commonRegs, i))
                # self.submodules.hbm_4 = HBMReadAndWriteSM(hbm.axi[i])
                self.add_csr(f"hbm_{i}")

            # setattr(self.submodules, f"hbm4", HBMReadAndWriteSM(hbm.axi[4]))
            # self.add_csr("hbm4")

            # self.submodules.hbm_fsm_vars = hbm_fsm_vars = HBMBISTStarter()
            # for i in range(0, 32):
            #     setattr(self.submodules, f"hbm_{i}", HBMBIST(hbm.axi[i], hbm_fsm_vars, i))
            #     # self.submodules.hbm_4 = HBMReadAndWriteSM(hbm.axi[i])
            #     self.add_csr(f"hbm_{i}")

            #####################################################################################

        analyzer_signals = [
            hbm.axi[0].aw,
            hbm.axi[0].w,
            hbm.axi[0].b,
            hbm.axi[0].ar,
            hbm.axi[0].r,
            self.hbm_0.prepwritecommand_fsm.status,
            self.hbm_1.prepwritecommand_fsm.status,
            self.hbm_2.prepwritecommand_fsm.status,
            self.hbm_3.prepwritecommand_fsm.status,
            self.hbm_4.prepwritecommand_fsm.status,
            self.hbm_5.prepwritecommand_fsm.status,
            self.hbm_6.prepwritecommand_fsm.status,
            self.hbm_7.prepwritecommand_fsm.status,
            self.hbm_8.prepwritecommand_fsm.status,
            self.hbm_9.prepwritecommand_fsm.status,
            self.hbm_10.prepwritecommand_fsm.status,
            self.hbm_11.prepwritecommand_fsm.status,
            self.hbm_12.prepwritecommand_fsm.status,
            self.hbm_13.prepwritecommand_fsm.status,
            self.hbm_14.prepwritecommand_fsm.status,
            self.hbm_15.prepwritecommand_fsm.status,
            self.hbm_16.prepwritecommand_fsm.status,
            self.hbm_17.prepwritecommand_fsm.status,
            self.hbm_18.prepwritecommand_fsm.status,
            self.hbm_19.prepwritecommand_fsm.status,
            self.hbm_20.prepwritecommand_fsm.status,
            self.hbm_21.prepwritecommand_fsm.status,
            self.hbm_22.prepwritecommand_fsm.status,
            self.hbm_23.prepwritecommand_fsm.status,
            self.hbm_24.prepwritecommand_fsm.status,
            self.hbm_25.prepwritecommand_fsm.status,
            self.hbm_26.prepwritecommand_fsm.status,
            self.hbm_27.prepwritecommand_fsm.status,
            self.hbm_28.prepwritecommand_fsm.status,
            self.hbm_29.prepwritecommand_fsm.status,
            self.hbm_30.prepwritecommand_fsm.status,
            self.hbm_31.prepwritecommand_fsm.status,
            self.hbm_0.prepreadcommand_fsm.status,
            self.hbm_1.prepreadcommand_fsm.status,
            self.hbm_2.prepreadcommand_fsm.status,
            self.hbm_3.prepreadcommand_fsm.status,
            self.hbm_4.prepreadcommand_fsm.status,
            self.hbm_5.prepreadcommand_fsm.status,
            self.hbm_6.prepreadcommand_fsm.status,
            self.hbm_7.prepreadcommand_fsm.status,
            self.hbm_8.prepreadcommand_fsm.status,
            self.hbm_9.prepreadcommand_fsm.status,
            self.hbm_10.prepreadcommand_fsm.status,
            self.hbm_11.prepreadcommand_fsm.status,
            self.hbm_12.prepreadcommand_fsm.status,
            self.hbm_13.prepreadcommand_fsm.status,
            self.hbm_14.prepreadcommand_fsm.status,
            self.hbm_15.prepreadcommand_fsm.status,
            self.hbm_16.prepreadcommand_fsm.status,
            self.hbm_17.prepreadcommand_fsm.status,
            self.hbm_18.prepreadcommand_fsm.status,
            self.hbm_19.prepreadcommand_fsm.status,
            self.hbm_20.prepreadcommand_fsm.status,
            self.hbm_21.prepreadcommand_fsm.status,
            self.hbm_22.prepreadcommand_fsm.status,
            self.hbm_23.prepreadcommand_fsm.status,
            self.hbm_24.prepreadcommand_fsm.status,
            self.hbm_25.prepreadcommand_fsm.status,
            self.hbm_26.prepreadcommand_fsm.status,
            self.hbm_27.prepreadcommand_fsm.status,
            self.hbm_28.prepreadcommand_fsm.status,
            self.hbm_29.prepreadcommand_fsm.status,
            self.hbm_30.prepreadcommand_fsm.status,
            self.hbm_31.prepreadcommand_fsm.status,
            self.hbm_0.total_writes.status,
            self.hbm_0.total_reads.status,
            self.hbm_0.ticks.status,
            self.hbm_0.delay_state_fsm.status,
            self.hbm_0.waitinstruction_fsm.status,
            self.hbm_0.port_settings.storage,
            self.hbm_0.port_id_const,
            self.hbm_0.port_num_array,
            self.hbm_0.exec_done.status,
            self.commonRegs.start.storage,
            self.hbm_0.ticks.status,


            # self.bus.slaves["hbm0"].adr,
            # self.bus.slaves["hbm0"].dat_w,
            # self.bus.slaves["hbm0"].dat_r,
            # self.bus.slaves["hbm0"].sel,
            # self.bus.slaves["hbm0"].cyc,
            # self.bus.slaves["hbm0"].stb,
            # self.bus.slaves["hbm0"].ack,
            # self.bus.slaves["hbm0"].we,
            # self.bus.slaves["hbm0"].cti,
            # self.bus.slaves["hbm0"].bte,
            # self.bus.slaves["hbm0"].err,

            # axi_lite_hbm.aw,
            # axi_lite_hbm.w,
            # axi_lite_hbm.b,
            # axi_lite_hbm.ar,
            # axi_lite_hbm.r,
            # self.cpu.ibus.stb,
            # self.cpu.ibus.cyc,
            # self.cpu.ibus.adr,
            # self.cpu.ibus.we,
            # self.cpu.ibus.ack,
            # self.cpu.ibus.sel,
            # self.cpu.ibus.dat_w,
            # self.cpu.ibus.dat_r,
            # self.cpu.dbus.stb,
            # self.cpu.dbus.cyc,
            # self.cpu.dbus.adr,
            # self.cpu.dbus.we,
            # self.cpu.dbus.ack,
            # self.cpu.dbus.sel,
            # self.cpu.dbus.dat_w,
            # self.cpu.dbus.dat_r,
        ]

        from litescope import LiteScopeAnalyzer
        self.submodules.analyzer = LiteScopeAnalyzer(analyzer_signals,
            depth = 2048,
            clock_domain="sys",
            samplerate=sys_clk_freq,
            csr_csv="analyzer.csv",
        )

        # analyzer_signals = [axi_lite_hbm.aw]

        # analyzer_depth = 128

        # analyzer_clock_domain = "sys"

        # self.submodules.analyzer = LiteScopeAnalyzer(analyzer_signals,
        #                                              analyzer_depth,
        #                                              clock_domain=analyzer_clock_domain)


        # PCIe -------------------------------------------------------------------------------------
        if with_pcie:
            self.pcie_phy = USPPCIEPHY(platform, platform.request("pcie_x4"),
                data_width = 256,
                bar0_size  = 0x20000)
            self.add_pcie(phy=self.pcie_phy, ndmas=1)

        # Leds -------------------------------------------------------------------------------------
        if with_led_chaser:
            self.leds = LedChaser(
                pads         = platform.request_all("gpio_led"),
                sys_clk_freq = sys_clk_freq)

# Build --------------------------------------------------------------------------------------------

def main():

    from litex.build.parser import LiteXArgumentParser
    parser = LiteXArgumentParser(platform=xilinx_alveo_u280.Platform, description="LiteX SoC on Alveo U280.")
    parser.add_target_argument("--sys-clk-freq",    default=150e6, type=float, help="System clock frequency.") # HBM2 with 250MHz, DDR4 with 150MHz (1:4)
    parser.add_target_argument("--ddram-channel",   default="0",               help="DDRAM channel (0, 1, 2 or 3).") # also selects clk 0 or 1
    parser.add_target_argument("--with-pcie",       action="store_true",       help="Enable PCIe support.")
    parser.add_target_argument("--driver",          action="store_true",       help="Generate PCIe driver.")
    parser.add_target_argument("--with-hbm",        action="store_true",       help="Use HBM2.")
    parser.add_target_argument("--with-analyzer",   action="store_true",       help="Enable Analyzer.")
    parser.add_target_argument("--with-led-chaser", action="store_true",       help="Enable LED Chaser.")
    # parser.add_target_argument("--with-litex-sim",  action="store_true",       help="Run simulation")
    args = parser.parse_args()

    args.csr_csv = "csr.csv"
    args.csr_address_width = 15

    # if args.with_litex_sim:
    #     sim_config = SimConfig()
    #     sim_config.add_clocker("sys_clk", freq_hz=args.sys_clk_freq)


    if args.with_hbm:
        args.sys_clk_freq = 250e6

    soc = BaseSoC(
        sys_clk_freq    = args.sys_clk_freq,
        ddram_channel   = int(args.ddram_channel, 0),
        with_pcie       = args.with_pcie,
        with_led_chaser = args.with_led_chaser,
        with_hbm        = args.with_hbm,
        with_analyzer   = args.with_analyzer,
        **parser.soc_argdict
	)
    builder = Builder(soc, **parser.builder_argdict)
    if args.build:
        vns = builder.build(**parser.toolchain_argdict)
        # sim_config   = SimConfig()
        # sim_config.add_clocker("sys_clk", freq_hz=sys_clk_freq)
        # builder.build(
        #     sim_config       = sim_config,
        #     interactive      = not args.non_interactive,
        #     pre_run_callback = pre_run_callback,
        #     **parser.toolchain_argdict,
        # )

        # soc.analyzer.export_csv(vns, "test/analyzer.csv")

    if args.driver:
        generate_litepcie_software(soc, os.path.join(builder.output_dir, "driver"))

    if args.load:
        prog = soc.platform.create_programmer()
        prog.load_bitstream(builder.get_bitstream_filename(mode="sram"))

if __name__ == "__main__":
    main()
