"""
HBM Port Access is meant to allow the HBM to be written over AXI Lite
following cues from the LiteDRAM code
"""
# pylint: disable = unused-wildcard-import
from migen import *

# pylint: disable = unused-wildcard-import
from litex.soc.interconnect.csr import *
from litex.soc.interconnect.axi import AXIInterface


ONE_BIT_WIDE = 1
TWO_BITS_WIDE = 2

class HBMCSRSCommon(Module, AutoCSR):
    def __init__(self):

        # Signal to set number of ports to use
        self.ports_mask = CSRStorage(32, description="Number of ports to use.")

        # Signal to start the test
        self.start = CSRStorage(1, description="Start the fsm")

        # Pattern 
        self.data_pattern = CSRStorage(32, description="Data pattern to write")

        self.delay_force = CSRStorage(
            1, description="Force running ports to delay to take statistics after a pause.",
        )


# For settings:
OPTION_WRITE = 1
OPTION_READ = 0

class HBMReadAndWriteSM(Module, AutoCSR):
    """
    A state machine to access the hbm in a read or write command.
    """

    # Here, axi_port is an AXIInterface object.
    def __init__(self, axi_port: AXIInterface, csrs_common: HBMCSRSCommon, port_id: int):

        self.data_sig_r = Signal(256)
        self.data_sig_w = Signal(256)
        self.strb_sig = Signal(32)
        self.beat_counter = Signal(12)
        self.burst_counter = Signal(32)
        self.port_num_array = Signal(32)
        self.port_id_const = Signal(32)
        self.delay_ctr = Signal(32)

        self.port_settings = CSRStorage(TWO_BITS_WIDE, description="Read/Write(LSB=0,1)")
        self.total_reads = CSRStatus(32, description="Count of total reads")
        self.total_writes = CSRStatus(32, description="Count of total writes")
        self.ticks = CSRStatus(
            32, description="Number of ticks taken for burst transaction",
        )
        # self.strb_readwrite = CSRStorage(
        #     axi_port.data_width // 8,
        #     description="Indicates the byte lanes that hold valid data",
        # )
        self.address_readwrite = CSRStorage(
            28, description="Address to perform read or write at"
        )
        # self.data_writein1 = CSRStorage(
        #     32, description="Data to write after performing write"
        # )
        # self.data_writein2 = CSRStorage(
        #     32, description="Data to write after performing write"
        # )
        # self.data_writein3 = CSRStorage(
        #     32, description="Data to write after performing write"
        # )
        # self.data_writein4 = CSRStorage(
        #     32, description="Data to write after performing write"
        # )
        # self.data_writein5 = CSRStorage(
        #     32, description="Data to write after performing write"
        # )
        # self.data_writein6 = CSRStorage(
        #     32, description="Data to write after performing write"
        # )
        # self.data_writein7 = CSRStorage(
        #     32, description="Data to write after performing write"
        # )
        # self.data_writein8 = CSRStorage(
        #     32, description="Data to write after performing write"
        # )
        self.data_readout1 = CSRStatus(
            32, description="Data to read after performing read"
        )
        self.data_readout2 = CSRStatus(
            32, description="Data to read after performing read"
        )
        self.data_readout3 = CSRStatus(
            32, description="Data to read after performing read"
        )
        self.data_readout4 = CSRStatus(
            32, description="Data to read after performing read"
        )
        self.data_readout5 = CSRStatus(
            32, description="Data to read after performing read"
        )
        self.data_readout6 = CSRStatus(
            32, description="Data to read after performing read"
        )
        self.data_readout7 = CSRStatus(
            32, description="Data to read after performing read"
        )
        self.data_readout8 = CSRStatus(
            32, description="Data to read after performing read"
        )
        self.exec_read_done = CSRStatus(
            ONE_BIT_WIDE, description="High if done performing read"
        )
        self.exec_done = CSRStatus(
            ONE_BIT_WIDE, description="High if done performing write"
        )
        self.acknowledge_readwrite = CSRStorage(
            ONE_BIT_WIDE,
            description="Acknowledge to state machine read or write happened",
        )
        self.burst_len = CSRStorage(
            12, # 4 bits wide
            description="Number of bursts (default burst size is 5, 2^5=32 bytes)"
        )
        self.last_burst_len = CSRStorage(
            12, description="Number of beats in last burst"
        )
        self.waitinstruction_fsm = CSRStatus(
            ONE_BIT_WIDE,
            description="FSM: Wait Stage",
        )
        self.prepwritecommand_fsm = CSRStatus(
            ONE_BIT_WIDE, 
            description="FSM: Stage 1 of write",
        )
        self.beat_fsm = CSRStatus(
            ONE_BIT_WIDE, 
            description="FSM: Stage 2 of write",
        )
        self.beat_fsm = CSRStatus(
            ONE_BIT_WIDE, 
            description="FSM: Stage 2 of write",
        )
        self.prepwriteresponse_fsm = CSRStatus(
            ONE_BIT_WIDE,
            description="FSM: Stage 3 of write",
        )
        self.donewrite_fsm = CSRStatus(
            ONE_BIT_WIDE, 
            description="FSM: Done with write",
        )
        self.prepreadcommand_fsm = CSRStatus(
            ONE_BIT_WIDE,
            description= "FSM: Stage 1 of read",
        )
        self.prepread_fsm = CSRStatus(
            ONE_BIT_WIDE,
            description="FSM: Stage 2 of read",
        )
        self.doneread_fsm = CSRStatus(
            ONE_BIT_WIDE,
            description="FSM: Done with read",
        )
        self.burst_quantity = CSRStorage(
            32, description="Number of bursts per command",
        )
        self.delay_ctr_max = CSRStorage(
            32, description="Number of clock cycles to delay after writing/reading bytes",
        )
        self.delay_state_fsm = CSRStatus(
            1, description="Number of clock cycles to delay after writing/reading bytes",
        )
        
        # Set number of ports to use
        self.comb += self.port_num_array.eq(csrs_common.ports_mask.storage)
        self.comb += self.port_id_const.eq(0x1 << (port_id))


        hbm_port_fsm = FSM(reset_state="WAIT_CMD")
        self.submodules.hbm_port_fsm = hbm_port_fsm

        # Set address, strobe, and possibly data_writein BEFORE performing read or write
        hbm_port_fsm.act(
            "WAIT_CMD",
            self.exec_done.status.eq(1),
            self.waitinstruction_fsm.status.eq(1),
            If((csrs_common.start.storage != 0) & (self.port_settings.storage == OPTION_READ), 
                If (self.port_id_const & self.port_num_array,
                    NextValue(self.burst_counter, 0),
                    NextValue(self.ticks.status, 0),
                    NextValue(self.total_writes.status, 0),
                    NextValue(self.total_reads.status, 0),
                    NextState("READ_VALID"),
                )
            ).Elif((csrs_common.start.storage != 0) & (self.port_settings.storage == OPTION_WRITE),
                If(self.port_id_const & self.port_num_array,
                    NextValue(self.beat_counter, 0),
                    NextValue(self.burst_counter, 0),
                    NextValue(self.ticks.status, 0),
                    NextValue(self.total_writes.status, 0),
                    NextValue(self.total_reads.status, 0),
                    NextState("WRITE_VALID"),
                )
            ).Else(
                NextValue(self.ticks.status, self.ticks.status),
                NextState("WAIT_CMD"),
            ),
        )
        hbm_port_fsm.act(
            "WRITE_VALID",
            self.prepwritecommand_fsm.status.eq(1),
            axi_port.aw.addr.eq(self.address_readwrite.storage << 5),
            axi_port.aw.valid.eq(1),
            axi_port.w.data.eq(self.data_sig_w),
            axi_port.w.strb.eq(self.strb_sig),
            axi_port.w.valid.eq(1),
            NextValue(self.ticks.status, self.ticks.status + 1),
            If(((axi_port.aw.ready & axi_port.w.ready) & (axi_port.aw.len > 0)),
                NextValue(self.beat_counter, self.beat_counter + 1),
                NextValue(self.total_writes.status, self.total_writes.status + 1),
                NextState("WRITE_BEAT"))
            .Elif((axi_port.aw.ready & axi_port.w.ready), 
                axi_port.w.last.eq(1),
                NextValue(self.total_writes.status, self.total_writes.status + 1),
                NextValue(self.burst_counter, self.burst_counter + 1),
                NextState("WRITE_LAST"),)
            .Else(
                NextState("WRITE_VALID"),
            ),
        )
        hbm_port_fsm.act(
            "WRITE_BEAT",
            self.beat_fsm.status.eq(1),
            axi_port.aw.addr.eq(self.address_readwrite.storage << 5),
            axi_port.w.data.eq(self.data_sig_w),
            axi_port.w.strb.eq(self.strb_sig),
            axi_port.w.valid.eq(1),
            NextValue(self.ticks.status, self.ticks.status + 1),
            If((axi_port.w.ready & (self.beat_counter < axi_port.aw.len)),
                NextValue(self.total_writes.status, self.total_writes.status + 1),
                NextValue(self.beat_counter, self.beat_counter + 1),
                NextState("WRITE_BEAT")
            ).Elif((axi_port.w.ready & (self.beat_counter == axi_port.aw.len)),
                axi_port.w.last.eq(1),
                NextValue(self.total_writes.status, self.total_writes.status + 1),
                NextValue(self.beat_counter, 0),
                NextValue(self.burst_counter, self.burst_counter + 1),
                NextState("WRITE_LAST"),
            ).Else(
                NextValue(self.total_writes.status, self.total_writes.status),
                NextState("WRITE_BEAT")
            )
        )
        hbm_port_fsm.act(
            "WRITE_LAST",
            self.prepwriteresponse_fsm.status.eq(1),
            axi_port.aw.addr.eq(self.address_readwrite.storage << 5),
            axi_port.w.data.eq(self.data_sig_w),
            axi_port.w.strb.eq(self.strb_sig),
            axi_port.w.valid.eq(0),
            axi_port.b.ready.eq(1),
            NextValue(self.ticks.status, self.ticks.status + 1),
            If(axi_port.b.valid & (self.burst_counter >= self.burst_quantity.storage), 
                If(csrs_common.start.storage == 0,
                    NextValue(self.total_writes.status, self.total_writes.status),
                    NextState("WAIT_CMD"),
                ).Elif((self.delay_ctr_max.storage > 0) | csrs_common.delay_force.storage,
                    NextValue(self.total_writes.status, self.total_writes.status),
                    NextValue(self.beat_counter, 0),
                    NextValue(self.burst_counter, 0),
                    NextValue(self.delay_ctr, 0),
                    NextState("WRITE_PAUSE"),
                ).Else(
                    NextValue(self.beat_counter, 0),
                    NextValue(self.burst_counter, 0),
                    NextValue(self.ticks.status, 0),
                    NextValue(self.total_writes.status, 0),
                    NextState("WRITE_VALID"),
                )
            ).Elif(axi_port.b.valid,
                NextValue(self.total_writes.status, self.total_writes.status),
                NextValue(self.beat_counter, 0),
                NextState("WRITE_VALID"),
            ).Else(
                NextValue(self.total_writes.status, self.total_writes.status),
                NextState("WRITE_LAST"),
            ),
        )
        hbm_port_fsm.act(
            "WRITE_PAUSE",
            self.delay_state_fsm.status.eq(1),
            NextValue(self.ticks.status, self.ticks.status),
            NextValue(self.total_writes.status, self.total_writes.status),
            If((self.delay_ctr_max.storage > 0) & ~csrs_common.delay_force.storage,
                NextValue(self.delay_ctr, self.delay_ctr + 1),
            ).Else(
                NextValue(self.delay_ctr, self.delay_ctr),
            ),
            If(csrs_common.start.storage == 0,
                NextState("WAIT_CMD"),   
            ).Elif(csrs_common.delay_force.storage, 
                NextState("WRITE_PAUSE"),
            ).Elif((self.delay_ctr_max == 0) & ~csrs_common.delay_force.storage,
                NextState("WRITE_VALID"),
            ).Elif(((self.delay_ctr + 1) >= self.delay_ctr_max.storage),
                NextState("WRITE_VALID"),
            )
        )
        # hbm_port_fsm.act(
        #     "DONE_TRANSACTION",
        #     NextValue(self.ticks.status, self.ticks.status),
        #     self.exec_done.status.eq(1),
        #     If((~csrs_common.start.storage),
        #         NextState("WAIT_CMD"),
        #     ).Else(
        #         NextState("DONE_TRANSACTION"),
        #     ),
        # )

        hbm_port_fsm.act(
            "READ_VALID",
            self.prepreadcommand_fsm.status.eq(1),
            axi_port.ar.valid.eq(1),
            axi_port.ar.addr.eq(self.address_readwrite.storage << 5),
            NextValue(self.ticks.status, self.ticks.status + 1),
            If(axi_port.ar.ready, 
                NextState("READ_BEAT"),
                NextValue(self.total_reads.status, self.total_reads.status),
            ).Else(
                NextValue(self.total_reads.status, self.total_reads.status),
                NextState("READ_VALID"),
            ),
        )
        hbm_port_fsm.act(
            "READ_BEAT",
            self.prepread_fsm.status.eq(1),
            axi_port.ar.addr.eq(self.address_readwrite.storage << 5),
            axi_port.r.ready.eq(1),
            NextValue(self.ticks.status, self.ticks.status + 1),
            If((axi_port.r.valid & axi_port.r.last),
                NextValue(self.burst_counter, self.burst_counter + 1),
                If(((self.burst_counter + 1) >= self.burst_quantity.storage),
                    If(csrs_common.start.storage == 0,
                        NextValue(self.total_reads.status, self.total_reads.status + 1),
                        NextState("WAIT_CMD"),
                    ).Elif((self.delay_ctr_max.storage > 0) | csrs_common.delay_force.storage,
                        NextValue(self.total_reads.status, self.total_reads.status + 1),
                        NextValue(self.beat_counter, 0),
                        NextValue(self.burst_counter, 0),
                        NextValue(self.delay_ctr, 0),
                        NextState("READ_PAUSE"),
                    ).Else(
                        NextValue(self.beat_counter, 0),
                        NextValue(self.burst_counter, 0),
                        NextValue(self.ticks.status, 0),
                        NextValue(self.total_reads.status, 0),
                        NextState("READ_VALID"),
                    )
                ).Else(
                    NextValue(self.total_reads.status, self.total_reads.status + 1),
                    NextValue(self.beat_counter, 0),
                    NextState("READ_VALID"),
                )
            ).Elif((axi_port.r.valid), 
                NextValue(self.total_reads.status, self.total_reads.status + 1),
                NextState("READ_BEAT"),
            ).Else(
                NextValue(self.total_reads.status, self.total_reads.status),
                NextState("READ_BEAT"),
            )
        )
        hbm_port_fsm.act(
            "READ_PAUSE",
            self.delay_state_fsm.status.eq(1),
            NextValue(self.ticks.status, self.ticks.status),
            NextValue(self.total_reads.status, self.total_reads.status),
            If((self.delay_ctr_max.storage > 0) & ~csrs_common.delay_force.storage,
                NextValue(self.delay_ctr, self.delay_ctr + 1),
            ).Else(
                NextValue(self.delay_ctr, self.delay_ctr),
            ),
            If(csrs_common.start.storage == 0,
                NextState("WAIT_CMD"),   
            ).Elif(csrs_common.delay_force.storage, 
                NextState("READ_PAUSE"),
            ).Elif((self.delay_ctr_max == 0) & ~csrs_common.delay_force.storage,
                NextState("READ_VALID"),
            ).Elif(((self.delay_ctr + 1) >= self.delay_ctr_max.storage),
                NextState("READ_VALID"),
            )
        )

        self.comb += [
            self.data_readout1.status.eq(self.data_sig_r[:32]),
            self.data_readout2.status.eq(self.data_sig_r[32:64]),
            self.data_readout3.status.eq(self.data_sig_r[64:96]),
            self.data_readout4.status.eq(self.data_sig_r[96:128]),
            self.data_readout5.status.eq(self.data_sig_r[128:160]),
            self.data_readout6.status.eq(self.data_sig_r[160:192]),
            self.data_readout7.status.eq(self.data_sig_r[192:224]),
            self.data_readout8.status.eq(self.data_sig_r[224:256]),

            self.data_sig_w[:32].eq(csrs_common.data_pattern.storage + self.beat_counter),
            self.data_sig_w[32:64].eq(csrs_common.data_pattern.storage),
            self.data_sig_w[64:96].eq(csrs_common.data_pattern.storage),
            self.data_sig_w[96:128].eq(csrs_common.data_pattern.storage),
            self.data_sig_w[128:160].eq(csrs_common.data_pattern.storage),
            self.data_sig_w[160:192].eq(csrs_common.data_pattern.storage),
            self.data_sig_w[192:224].eq(csrs_common.data_pattern.storage),
            self.data_sig_w[224:256].eq(csrs_common.data_pattern.storage),

            self.strb_sig.eq(0xffffffff)

            # self.data_sig_w[:32].eq(self.data_writein1.storage),
            # self.data_sig_w[32:64].eq(self.data_writein2.storage),
            # self.data_sig_w[64:96].eq(self.data_writein3.storage),
            # self.data_sig_w[96:128].eq(self.data_writein4.storage),
            # self.data_sig_w[128:160].eq(self.data_writein5.storage),
            # self.data_sig_w[160:192].eq(self.data_writein6.storage),
            # self.data_sig_w[192:224].eq(self.data_writein7.storage),
            # self.data_sig_w[224:256].eq(self.data_writein8.storage),
        ]

        ##############################################################
        # Defaults for AXI3
        ##############################################################

        burst_type="INCR"

        burst_type = {
            "FIXED": 0b00,
            "INCR":  0b01,
            "WRAP":  0b10,
        }[burst_type]

        burst_size = log2_int(axi_port.data_width // 8)

        prot = 0

        write_id = 0
        read_id = 0

        self.comb += [
            axi_port.aw.burst.eq(burst_type), 
            axi_port.aw.size.eq(burst_size), # Number of bytes (-1) of each data transfer (up to 1024-bit).
            axi_port.aw.lock.eq(0),  # Normal access
            axi_port.aw.prot.eq(prot),
            axi_port.aw.cache.eq(0b0011),  # Normal Non-cacheable Bufferable
            axi_port.aw.qos.eq(0),
            axi_port.aw.id.eq(write_id),

            axi_port.ar.burst.eq(burst_type),
            axi_port.ar.size.eq(burst_size),
            axi_port.ar.lock.eq(0),
            axi_port.ar.prot.eq(prot),
            axi_port.ar.cache.eq(0b0011),
            axi_port.ar.qos.eq(0),
            axi_port.ar.id.eq(read_id),

            # Select last 
            If((self.burst_counter >= self.burst_quantity.storage - 1) & (self.last_burst_len.storage > 0),
                axi_port.aw.len.eq(self.last_burst_len.storage - 1), # Subtract one as last_burst specifies actual number of bursts 
                axi_port.ar.len.eq(self.last_burst_len.storage - 1), # and len takes 0xf as 16 or 0x0 as 1 beat per transaction.
            ).Else(
                axi_port.aw.len.eq(self.burst_len.storage - 1),
                axi_port.ar.len.eq(self.burst_len.storage - 1),
            ),
        ]

    


# # def ax_description(address_width, version="axi4"):
# #     len_width  = {"axi3":4, "axi4":8}[version]
# #     size_width = {"axi3":4, "axi4":3}[version]
# #     lock_width = {"axi3":2, "axi4":1}[version]
# #     # * present for interconnect with others cores but not used by LiteX.
# #     return [
# #         ("addr",   address_width),   # Address Width.
# #         ("burst",  2),               # Burst type.
# #         ("len",    len_width),       # Number of data (-1) transfers (up to 16 (AXI3) or 256 (AXI4)).
# #         ("size",   size_width),      # Number of bytes (-1) of each data transfer (up to 1024-bit).
# #         ("lock",   lock_width),      # *
# #         ("prot",   3),               # *
# #         ("cache",  4),               # *
# #         ("qos",    4),               # *
# #         ("region", 4),               # *
# #     ]

# # def w_description(data_width):
# #     return [
# #         ("data", data_width),
# #         ("strb", data_width//8),
# #     ]

# # def b_description():
# #     return [("resp", 2)]

# # def r_description(data_width):
# #     return [
# #         ("resp", 2),
# #         ("data", data_width),
# #     ]

#     #         def write(self, addr, data, strb=None):
#     #     if strb is None:
#     #         strb = 2**len(self.w.strb) - 1
#     #     # aw + w
#     #     yield self.aw.valid.eq(1)
#     #     yield self.aw.addr.eq(addr)
#     #     yield self.w.data.eq(data)
#     #     yield self.w.valid.eq(1)
#     #     yield self.w.strb.eq(strb)
#     #     yield
#     #     while not (yield self.aw.ready):
#     #         yield
#     #     yield self.aw.valid.eq(0)
#     #     yield self.aw.addr.eq(0)
#     #     while not (yield self.w.ready):
#     #         yield
#     #     yield self.w.valid.eq(0)
#     #     yield self.w.strb.eq(0)
#     #     # b
#     #     yield self.b.ready.eq(1)
#     #     while not (yield self.b.valid):
#     #         yield
#     #     resp = (yield self.b.resp)
#     #     yield self.b.ready.eq(0)
#     #     return resp

#     # def read(self, addr):
#     #     # ar
#     #     yield self.ar.valid.eq(1)
#     #     yield self.ar.addr.eq(addr)
#     #     yield
#     #     while not (yield self.ar.ready):
#     #         yield
#     #     yield self.ar.valid.eq(0)
#     #     # r
#     #     yield self.r.ready.eq(1)
#     #     while not (yield self.r.valid):
#     #         yield
#     #     data = (yield self.r.data)
#     #     resp = (yield self.r.resp)
#     #     yield self.r.ready.eq(0)
#     #     return (data, resp)


# DATA_256_BITS = 256
# FULL_DATA_CONTAINER = 4096
# OPTION_1A = 0 # write / read
# OPTION_1B = 3 # write / read
# OPTION_2 = 1  # write
# OPTION_3 = 2  # read

# class HBMBISTStarter(Module, AutoCSR):
#     """
#     A state machine that acts as a continuous reader, writer, or bist.
#     """

#     # Here, axi_port is an AXILite object, to be used with AXILite2AXI.
#     def __init__(self):
#         self.start = CSRStorage(
#             ONE_BIT_WIDE, description="Start the BIST. Flip to turn it off."
#         )
#         self.rw_enable = CSRStorage(
#             TWO_BITS_WIDE, description="00, 11 = Enable both reading/writing, 01 = Enable writing, 10 = Enable reading"
#         )
#         self.strb = CSRStorage(
#             32, description="The valid bytes to write to."
#         )
#         self.port_num_enable = CSRStorage(
#             32, description="Number to set every bit which represents one port being used (LSB=first port)."
#         )
#         self.address_base = CSRStorage(
#             28, description="Base address, first port being used will use this one."
#         )
#         self.address_length = CSRStorage(
#             28, description="Length of addresses that every port will write to from their starting address."
#         )
#         self.address_offset = CSRStorage(
#             28, description="Offset address, every port after the first port will begin with the base + (offset * port number)"
#         )
#         self.data_type = CSRStorage(
#             2, description="Data type to write: 00, 11 = Fixed, 01 = Incr, 10 = Random"
#         )
#         self.data_pattern = CSRStorage(
#             32, description="For use when data type is set to fixed, this will set the data pattern type."
#         )

#         # Signal to set number of ports to use
#         self.port_num_array = Signal(32)
    

# class HBMBIST(Module, AutoCSR):
#     def __init__(self, axi_port: AXIInterface, starterObject: HBMBISTStarter, port_num: int):

#         self.delay = CSRStorage(
#             32, description="The number of cycles to delay after a read or write."
#         )
#         self.num_transactions = CSRStorage(
#             32, description="The number of reads, writes, or both that should run (depending on the setting)"
#         )
#         self.total_writes = CSRStatus(
#             32, description="The total number of writes that have occured."
#         )
#         self.total_reads = CSRStatus(
#             32, description="The total number of reads that have occured."
#         )
#         self.total_ticks = CSRStatus(
#             32, description="The total number of ticks that have occured."
#         )
#         self.done = CSRStatus(
#             ONE_BIT_WIDE, description="Goes high when fsm has finished."
#         )


#         # Data to write
#         self.data_write = Signal(256)
        
#         # Address to read/write to
#         self.address = Signal(32)
#         self.next_address = Signal(28)

#         # Burst counter
#         self.burst_counter = Signal(32)
#         self.delay_counter = Signal(32)

#         # Number of transactions counter, 0 counts as 1 transaction.
#         self.num_transactions_counter = Signal(32)

#         # Variables to hold data and counter for BIST
#         self.data_check = Signal(4096)
#         self.data_counter = Signal(32)
#         self.data_reset = Signal()

#         # Helper to know what state we are in
#         self.state_info = Signal(4)

#         # Helpful constant for port number
#         self.port_num = port_num



#         hbm_bist_fsm = FSM(reset_state="BIST_IDLE")
#         self.submodules.hbm_bist_fsm = hbm_bist_fsm

#         # Wait here and hold data until we do a read or write.
#         # If a write test, start write axi protocol, otherwise 
#         # start the read axi protocol.
#         hbm_bist_fsm.act(
#             "BIST_IDLE",
#             self.state_info.eq(0),
#             If(starterObject.start.storage & (starterObject.port_num_array & (0x1 << self.port_num)),
#                 NextValue(self.total_writes.status, 0),
#                 NextValue(self.total_reads.status, 0),
#                 NextValue(self.total_ticks.status, 0),
#                 NextValue(self.next_address, 0),
#                 NextValue(self.data_reset, 1),
#                 NextValue(self.num_transactions_counter, self.num_transactions.storage),
#                 If((starterObject.rw_enable.storage == OPTION_1A) | 
#                    (starterObject.rw_enable.storage == OPTION_1B) |
#                    (starterObject.rw_enable.storage == OPTION_2),
#                     NextState("WRITE_VALID"),
#                 ).Elif (starterObject.rw_enable.storage == OPTION_3,
#                     NextState("READ_VALID"),      
#                 )
#             ).Else(
#                 NextValue(self.total_writes.status, self.total_writes.status),
#                 NextValue(self.total_reads.status, self.total_reads.status),
#                 NextValue(self.total_ticks.status, self.total_ticks.status),
#             )
#         )

#         # Set aw and w valid to high, wait for ready signals.
#         # If both go high and a burst write is performed,
#         # continue to set w valid high, else wait for write response.
#         hbm_bist_fsm.act(
#             "WRITE_VALID",
#             self.state_info.eq(1),
#             NextValue(self.total_reads.status, self.total_reads.status),
#             NextValue(self.total_ticks.status, self.total_ticks.status + 1),
#             NextValue(self.data_reset, 0),
#             axi_port.aw.addr.eq(self.address),
#             axi_port.aw.valid.eq(1),
#             axi_port.w.data.eq(self.data_write),
#             axi_port.w.strb.eq(starterObject.strb.storage),
#             axi_port.w.valid.eq(1),
#             If((axi_port.aw.ready & axi_port.w.ready) & (axi_port.aw.len > 0),
#                 NextValue(self.burst_counter, self.burst_counter + 1),
#                 NextValue(self.total_writes.status, self.total_writes.status + 1),
#                 If(self.next_address == starterObject.address_length.storage,
#                     NextValue(self.next_address, 0),
#                 ).Else(
#                     NextValue(self.next_address, self.next_address + 1),
#                 ),
#                 If(starterObject.rw_enable.storage == OPTION_2,
#                     NextValue(self.num_transactions_counter, self.num_transactions_counter - 1),
#                 ),
#                 NextState("WRITE_BURST_BEAT"),
#             ).Elif((axi_port.aw.ready & axi_port.w.ready),
#                 axi_port.w.last.eq(1),
#                 NextValue(self.total_writes.status, self.total_writes.status + 1),
#                 If(self.next_address == starterObject.address_length.storage,
#                     NextValue(self.next_address, 0),
#                 ).Else(
#                     NextValue(self.next_address, self.next_address + 1),
#                 ),
#                 If(starterObject.rw_enable.storage == OPTION_2,
#                     NextValue(self.num_transactions_counter, self.num_transactions_counter - 1),
#                 ),
#                 NextState("WRITE_RESPONSE"),
#             ).Else(
#                 NextValue(self.total_writes.status, self.total_writes.status),
#                 NextState("WRITE_VALID"),
#             )
#         )

#         # Continue doing burst writes until the counter reaches the user's configured
#         # number. Then move on to get the write response.
#         hbm_bist_fsm.act(
#             "WRITE_BURST_BEAT",
#             self.state_info.eq(2),
#             NextValue(self.total_reads.status, self.total_reads.status),
#             NextValue(self.total_ticks.status, self.total_ticks.status + 1),
#             axi_port.aw.addr.eq(self.address),
#             axi_port.aw.valid.eq(1),
#             axi_port.w.data.eq(self.data_write),
#             axi_port.w.strb.eq(starterObject.strb.storage),
#             axi_port.w.valid.eq(1),
#             NextValue(self.delay_counter, 0),
#             If(axi_port.w.ready & (self.burst_counter < axi_port.aw.len),
#                 NextValue(self.burst_counter, self.burst_counter + 1),
#                 NextValue(self.total_writes.status, self.total_writes.status + 1),
#                 If(self.next_address == starterObject.address_length.storage,
#                     NextValue(self.next_address, 0),
#                 ).Else(
#                     NextValue(self.next_address, self.next_address + 1),
#                 ),
#                 If(starterObject.rw_enable.storage == OPTION_2,
#                     NextValue(self.num_transactions_counter, self.num_transactions_counter - 1),
#                 ),
#                 NextState("WRITE_BURST_BEAT"),
#             ).Elif(axi_port.w.ready & (self.burst_counter == axi_port.aw.len),
#                 axi_port.w.last.eq(1),
#                 NextValue(self.burst_counter, 0),
#                 NextValue(self.total_writes.status, self.total_writes.status + 1),
#                 If(self.next_address == starterObject.address_length.storage,
#                     NextValue(self.next_address, 0),
#                 ).Else(
#                     NextValue(self.next_address, self.next_address + 1),
#                 ),
#                 If(starterObject.rw_enable.storage == OPTION_2,
#                     NextValue(self.num_transactions_counter, self.num_transactions_counter - 1),
#                 ),
#                 NextState("WRITE_RESPONSE"),
#             ).Else(
#                 NextValue(self.total_writes.status, self.total_writes.status),
#                 NextState("WRITE_BURST_BEAT"),
#             )
#         )

#         # After getting write response, do one of the following:
#         # 1. Finish if rw_enable is set to 'write' setting.
#         # 2. If a delay is set, go to this state and wait.
#         # 3. Else if the read/write setting is enabled, begin read.
#         # 4. Else start another write.
#         hbm_bist_fsm.act(
#             "WRITE_RESPONSE",
#             self.state_info.eq(3),
#             NextValue(self.total_writes.status, self.total_writes.status),
#             NextValue(self.total_reads.status, self.total_reads.status),
#             NextValue(self.total_ticks.status, self.total_ticks.status + 1),
#             axi_port.b.ready.eq(1),
#             If(axi_port.b.valid,
#                 If((starterObject.rw_enable.storage == OPTION_2) & 
#                    (self.num_transactions_counter == 0), # Done with transactions
#                     NextState("FINISHED"), 
#                 ).Elif(self.delay.storage > 0,
#                     NextValue(self.delay_counter, self.delay_counter + 1),
#                     NextState("WRITE_DELAY"),
#                 ).Elif((starterObject.rw_enable.storage == OPTION_1A) | 
#                        (starterObject.rw_enable.storage == OPTION_1B),
#                     NextState("READ_VALID"),
#                 ).Else(
#                     NextState("WRITE_VALID"),
#                 )
#             )
#         )

#         # Wait for the correct amount of time, then do one of the following:
#         # 1. Go to BIST IDLE if fsm is disabled.
#         # 2. Else if the read/write setting is enabled, begin read.
#         # 3. Else start another write.
#         hbm_bist_fsm.act(
#             "WRITE_DELAY",
#             self.state_info.eq(4),
#             NextValue(self.total_writes.status, self.total_writes.status),
#             NextValue(self.total_reads.status, self.total_reads.status),
#             NextValue(self.total_ticks.status, self.total_ticks.status + 1),
#             NextValue(self.delay_counter, self.delay_counter + 1),
#             If(self.delay_counter == self.delay.storage,
#                 If(~starterObject.start.storage,
#                     NextState("BIST_IDLE"),   
#                 ).Elif((starterObject.rw_enable.storage == OPTION_1A) | 
#                        (starterObject.rw_enable.storage == OPTION_1B),
#                     NextState("READ_VALID"),
#                 ).Else(
#                     NextState("WRITE_VALID"),
#                 )
#             )
#         )

#         # Set ar valid high with the address, and wait for ar ready and move on.
#         hbm_bist_fsm.act(
#             "READ_VALID",
#             self.state_info.eq(5),
#             NextValue(self.total_writes.status, self.total_writes.status),
#             NextValue(self.total_reads.status, self.total_reads.status),
#             NextValue(self.total_ticks.status, self.total_ticks.status + 1),
#             NextValue(self.data_reset, 0),
#             axi_port.ar.valid.eq(1),
#             axi_port.ar.addr.eq(self.address),
#             If(axi_port.ar.ready, 
#                 NextState("READ_RESPONSE"),
#             )
#         )

#         # If we have performed the correct number of reads through bursts, 
#         # do one of the following:
#         # 1. Finish if rw_enable is set to 'read' or 'write/read' setting.
#         # 2. If a delay is set, go to this state and wait.
#         # 3. Else if the read/write setting is enabled, begin write.
#         # 4. Else start another read.
#         hbm_bist_fsm.act(
#             "READ_RESPONSE",
#             self.state_info.eq(6),
#             NextValue(self.total_writes.status, self.total_writes.status),
#             NextValue(self.total_ticks.status, self.total_ticks.status + 1),
#             axi_port.r.ready.eq(1),
#             axi_port.ar.addr.eq(self.address),
#             If(axi_port.r.valid & axi_port.r.last,
#                 If(((starterObject.rw_enable.storage == OPTION_3) & (self.next_address == starterObject.address_length.storage)),
#                     NextValue(self.next_address, 0),
#                 ).Elif((starterObject.rw_enable.storage == OPTION_3),
#                     NextValue(self.next_address, self.next_address + 1),
#                 ),
#                 NextValue(self.total_reads.status, self.total_reads.status + 1),
#                 NextValue(self.num_transactions_counter, self.num_transactions_counter - 1),
#                 If(((starterObject.rw_enable.storage == OPTION_1A) |
#                        (starterObject.rw_enable.storage == OPTION_1B) |
#                        (starterObject.rw_enable.storage == OPTION_3)) & 
#                        (self.num_transactions_counter == 1), # Last transaction
#                     NextState("FINISHED"),   
#                 ).Elif(self.delay.storage > 0,
#                     NextValue(self.delay_counter, 0),
#                     NextState("READ_DELAY"),
#                 ).Elif((starterObject.rw_enable.storage == OPTION_1A) | 
#                        (starterObject.rw_enable.storage == OPTION_1B),
#                     NextValue(self.data_reset, 1),
#                     NextState("WRITE_VALID"),
#                 ).Else(
#                     NextState("READ_VALID"),
#                 )
#             ).Elif(axi_port.r.valid,
#                 If(((starterObject.rw_enable.storage == OPTION_3) & (self.next_address == starterObject.address_length.storage)),
#                     NextValue(self.next_address, 0)
#                 ).Elif((starterObject.rw_enable.storage == OPTION_3),
#                     NextValue(self.next_address, self.next_address + 1),
#                 ),
#                 NextValue(self.total_reads.status, self.total_reads.status + 1),
#                 NextValue(self.num_transactions_counter, self.num_transactions_counter - 1),
#             )
#         )

#         # Delay for the correct amount of clock cycles, then do the following:
#         # 1. Go to BIST IDLE if fsm is disabled.
#         # 3. Else if the read/write setting is enabled, begin write.
#         # 4. Else start another read.
#         hbm_bist_fsm.act(
#             "READ_DELAY",
#             self.state_info.eq(7),
#             NextValue(self.total_writes.status, self.total_writes.status),
#             NextValue(self.total_reads.status, self.total_reads.status),
#             NextValue(self.total_ticks.status, self.total_ticks.status + 1),
#             NextValue(self.delay_counter, self.delay_counter + 1),
#             If(self.delay_counter == self.delay.storage,
#                 If(~starterObject.start.storage,
#                     NextState("BIST_IDLE"),   
#                 ).Elif((starterObject.rw_enable.storage == OPTION_1A) | 
#                        (starterObject.rw_enable.storage == OPTION_1B),
#                     NextValue(self.data_reset, 1),
#                     NextState("WRITE_VALID"),
#                 ).Else(
#                     NextState("READ_VALID"),
#                 )
#             )
#         )

#         self.address = CSRStorage(28, description="Rightmost 28 bits of hbm address, will be shifted by 5")
#         self.data = CSRStorage(32, description="32 bits of data (max storage of csrstorage)")
#         self.perform_write = CSRStorage(ONE_BIT_WIDE, description="Start performing a write")
#         self.perform_read = CSRStorage(ONE_BIT_WIDE, description="Start to perform a read")
#         self.error_occured = CSRStatus(ONE_BIT_WIDE, description="Error occured")

        


#         )

#         # self.address_base = CSRStorage(
#         #     28, description="Base address, first port being used will use this one."
#         # )
#         # self.address_length = CSRStorage(
#         #     28, description="Length of addresses that every port will write to from their starting address."
#         # )
#         # self.address_offset = CSRStorage(
#         #     28, description="Offset address, every port after the first port will begin with the base + (offset * port number)"
#         # )

#         # Defaults for now, add more later.
#         # Only 28 bits in 33 bit address are usable, so shift 28 bit signals left by 5.
#         self.comb += [
#             self.data_write.eq((starterObject.data_pattern.storage << 16) + (0xff - self.burst_counter)),
#             starterObject.port_num_array.eq(~((~0) << starterObject.port_num_enable.storage)),
#             self.address.eq((starterObject.address_base.storage + 
#                                  (starterObject.address_offset.storage * self.port_num) + 
#                                  self.next_address) << 5),
#             If((self.num_transactions_counter > 0x10),
#                 axi_port.aw.len.eq(0xf),
#             ).Else(
#                 axi_port.aw.len.eq(self.num_transactions_counter - 1),
#             )
#         ]



