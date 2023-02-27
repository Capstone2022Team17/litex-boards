"""
HBM Port Access is meant to allow the HBM to be written over AXI Lite
following cues from the LiteDRAM code
"""
# pylint: disable = unused-wildcard-import
from migen import *

# pylint: disable = unused-wildcard-import
from litex.soc.interconnect.csr import *


ONE_BIT_WIDE = 1
TWO_BITS_WIDE = 2


class HBMReadAndWriteSM(Module, AutoCSR):
    """
    A state machine to access the hbm in a read or write command.
    """

    # Here, axi_port is an AXILite object, to be used with AXILite2AXI.
    def __init__(self, axi_port):

        self.data_sig_r = Signal(256)
        self.data_sig_w = Signal(256)
        self.strb_sig = Signal(32)

        self.perform_write = CSRStorage(ONE_BIT_WIDE, description="Perform a write")
        self.perform_read = CSRStorage(ONE_BIT_WIDE, description="Perform a read")
        self.write_resp = CSRStatus(TWO_BITS_WIDE, description="Response after writing")
        self.read_resp = CSRStatus(TWO_BITS_WIDE, description="Response after read")
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
        self.exec_write_done = CSRStatus(
            ONE_BIT_WIDE, description="High if done performing write"
        )
        self.acknowledge_readwrite = CSRStorage(
            ONE_BIT_WIDE,
            description="Acknowledge to state machine read or write happened",
        )
        self.waitinstruction_fsm = CSRStatus(
            ONE_BIT_WIDE,
            description="FSM: Wait Stage",
        )
        self.prepwritecommand_fsm = CSRStatus(
            ONE_BIT_WIDE, 
            description="FSM: Stage 1 of write",
        )
        # self.prepwrite_fsm = CSRStatus(
        #     ONE_BIT_WIDE, 
        #     description="FSM: Stage 2 of write",
        # )
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

        hbm_port_fsm = FSM(reset_state="WAIT_INSTRUCTION")
        self.submodules.hbm_port_fsm = hbm_port_fsm

        # Set address, strobe, and possibly data_writein BEFORE performing read or write
        hbm_port_fsm.act(
            "WAIT_INSTRUCTION",
            self.waitinstruction_fsm.status.eq(1),
            If(
                self.perform_read.storage,
                NextState("PERFORM_READ_COMMAND"),
            )
            .Elif(
                self.perform_write.storage,
                NextState("PREPARE_WRITE_COMMAND"),
            )
            .Else(
                NextState("WAIT_INSTRUCTION"),
            ),
        )
        # hbm_port_fsm.act(
        #     "EXTEND_ADDRESS_SIG",
        #     axi_port.w.data.eq(self.data_sig_w),
        #     axi_port.aw.addr.eq(self.address_readwrite.storage << 5),
        #     axi_port.w.strb.eq(self.strb_readwrite.storage),
        #     NextState("PREPARE_WRITE_COMMAND"),
        # )
        hbm_port_fsm.act(
            "PREPARE_WRITE_COMMAND",
            self.prepwritecommand_fsm.status.eq(1),
            axi_port.aw.addr.eq(self.address_readwrite.storage << 5),
            axi_port.aw.valid.eq(1),
            axi_port.w.data.eq(self.data_sig_w),
            axi_port.w.strb.eq(self.strb_sig),
            axi_port.w.valid.eq(1),
            If((axi_port.aw.ready & axi_port.w.ready), NextState("PREPARE_W_RESPONSE"),).Else(
                NextState("PREPARE_WRITE_COMMAND"),
            ),
        )
        # hbm_port_fsm.act(
        #     "CONTINUE_WRITE_COMMAND",
        #     axi_port.aw.addr.eq(self.address_readwrite.storage << 5),
        #     axi_port.w.data.eq(self.data_sig_w),
        #     axi_port.w.strb.eq(self.strb_readwrite.storage),
        #     axi_port.w.valid.eq(1),
        #     axi_port.aw.valid.eq(0),
        #     If((axi_port.w.ready), NextState("PREPARE_W_RESPONSE"),).Else(
        #         NextState("CONTINUE_WRITE_COMMAND"),
        #     ),
        # )
        hbm_port_fsm.act(
            "PREPARE_W_RESPONSE",
            self.prepwriteresponse_fsm.status.eq(1),
            axi_port.aw.addr.eq(self.address_readwrite.storage << 5),
            axi_port.w.data.eq(self.data_sig_w),
            axi_port.w.strb.eq(self.strb_sig),
            axi_port.w.valid.eq(0),
            #axi_port.b.ready.eq(1),
            If(axi_port.b.valid, NextState("DONE_WRITE")).Else(
                NextState("PREPARE_W_RESPONSE")
            ),
        )
        hbm_port_fsm.act(
            "DONE_WRITE",
            axi_port.b.ready.eq(1),
            axi_port.aw.addr.eq(self.address_readwrite.storage << 5),
            axi_port.w.data.eq(self.data_sig_w),
            axi_port.w.strb.eq(self.strb_sig),
            NextState("WAIT_ACK_W"),
        )
        hbm_port_fsm.act(
            "WAIT_ACK_W",
            self.donewrite_fsm.status.eq(1),
            self.exec_write_done.status.eq(1),
            self.write_resp.status.eq(axi_port.b.resp),
            If(self.acknowledge_readwrite.storage, NextState("WAIT_INSTRUCTION"),).Else(
                NextState("WAIT_ACK_W"),
            ),
        )

        hbm_port_fsm.act(
            "PERFORM_READ_COMMAND",
            self.prepreadcommand_fsm.status.eq(1),
            axi_port.ar.valid.eq(1),
            # axi_port.r.ready.eq(1),
            axi_port.ar.addr.eq(self.address_readwrite.storage << 5),
            If(axi_port.ar.ready, NextState("PERFORM_READ")).Else(
                NextState("PERFORM_READ_COMMAND")
            ),
        )
        hbm_port_fsm.act(
            "PERFORM_READ",
            self.prepread_fsm.status.eq(1),
            axi_port.ar.addr.eq(self.address_readwrite.storage << 5),
            # axi_port.r.ready.eq(1),
            self.exec_read_done.status.eq(1),
            self.data_sig_r.eq(axi_port.r.data),
            self.read_resp.status.eq(axi_port.r.resp),
            If(axi_port.r.valid & self.acknowledge_readwrite.storage, NextState("DONE_READ")).Else(
                NextState("PERFORM_READ")
            ),
        )
        hbm_port_fsm.act(
            "DONE_READ",
            self.doneread_fsm.status.eq(1),
            axi_port.ar.addr.eq(self.address_readwrite.storage << 5),
            axi_port.r.ready.eq(1),
            NextState("WAIT_INSTRUCTION"),
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

            self.data_sig_w[:32].eq(0x11111111),
            self.data_sig_w[32:64].eq(0x22222222),
            self.data_sig_w[64:96].eq(0x33333333),
            self.data_sig_w[96:128].eq(0x44444444),
            self.data_sig_w[128:160].eq(0x55555555),
            self.data_sig_w[160:192].eq(0x66666666),
            self.data_sig_w[192:224].eq(0x77777777),
            self.data_sig_w[224:256].eq(0x88888888),

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
            axi_port.aw.len.eq(0),  # Number of data (-1) transfers (up to 16 (AXI3) or 256 (AXI4)), currently 1 transfer per burst
            axi_port.aw.size.eq(burst_size), # Number of bytes (-1) of each data transfer (up to 1024-bit).
            axi_port.aw.lock.eq(0),  # Normal access
            axi_port.aw.prot.eq(prot),
            axi_port.aw.cache.eq(0b0011),  # Normal Non-cacheable Bufferable
            axi_port.aw.qos.eq(0),
            axi_port.aw.id.eq(write_id),

            axi_port.w.last.eq(1),

            axi_port.ar.burst.eq(burst_type),
            axi_port.ar.len.eq(0),
            axi_port.ar.size.eq(burst_size),
            axi_port.ar.lock.eq(0),
            axi_port.ar.prot.eq(prot),
            axi_port.ar.cache.eq(0b0011),
            axi_port.ar.qos.eq(0),
            axi_port.ar.id.eq(read_id),
        ]

    


# def ax_description(address_width, version="axi4"):
#     len_width  = {"axi3":4, "axi4":8}[version]
#     size_width = {"axi3":4, "axi4":3}[version]
#     lock_width = {"axi3":2, "axi4":1}[version]
#     # * present for interconnect with others cores but not used by LiteX.
#     return [
#         ("addr",   address_width),   # Address Width.
#         ("burst",  2),               # Burst type.
#         ("len",    len_width),       # Number of data (-1) transfers (up to 16 (AXI3) or 256 (AXI4)).
#         ("size",   size_width),      # Number of bytes (-1) of each data transfer (up to 1024-bit).
#         ("lock",   lock_width),      # *
#         ("prot",   3),               # *
#         ("cache",  4),               # *
#         ("qos",    4),               # *
#         ("region", 4),               # *
#     ]

# def w_description(data_width):
#     return [
#         ("data", data_width),
#         ("strb", data_width//8),
#     ]

# def b_description():
#     return [("resp", 2)]

# def r_description(data_width):
#     return [
#         ("resp", 2),
#         ("data", data_width),
#     ]

    #         def write(self, addr, data, strb=None):
    #     if strb is None:
    #         strb = 2**len(self.w.strb) - 1
    #     # aw + w
    #     yield self.aw.valid.eq(1)
    #     yield self.aw.addr.eq(addr)
    #     yield self.w.data.eq(data)
    #     yield self.w.valid.eq(1)
    #     yield self.w.strb.eq(strb)
    #     yield
    #     while not (yield self.aw.ready):
    #         yield
    #     yield self.aw.valid.eq(0)
    #     yield self.aw.addr.eq(0)
    #     while not (yield self.w.ready):
    #         yield
    #     yield self.w.valid.eq(0)
    #     yield self.w.strb.eq(0)
    #     # b
    #     yield self.b.ready.eq(1)
    #     while not (yield self.b.valid):
    #         yield
    #     resp = (yield self.b.resp)
    #     yield self.b.ready.eq(0)
    #     return resp

    # def read(self, addr):
    #     # ar
    #     yield self.ar.valid.eq(1)
    #     yield self.ar.addr.eq(addr)
    #     yield
    #     while not (yield self.ar.ready):
    #         yield
    #     yield self.ar.valid.eq(0)
    #     # r
    #     yield self.r.ready.eq(1)
    #     while not (yield self.r.valid):
    #         yield
    #     data = (yield self.r.data)
    #     resp = (yield self.r.resp)
    #     yield self.r.ready.eq(0)
    #     return (data, resp)


class HBMAXILiteAccess(Module, AutoCSR):
    """
    This allows most the signals in the AxiInterface (with others set to defaults as done
    in AxiLite2Axi) to be manipulated to write to the hbm controller.
    """

    # Here, axi_port is one of the 32 AXIInterface objects from the hbm variable.
    def __init__(self, axi_port):

        # This is the declaration of all the csr registers we will read and write to.
        # For now, this is simply a way to connect to all the registers of AXI Lite.
        # A migen state machine will likely be applied later for these.

        # CSR Status = What to read from
        # CSR Storage = What to write to

        # Write command
        self.aw_valid = CSRStorage(ONE_BIT_WIDE, description="Write Command valid")
        self.aw_ready = CSRStatus(ONE_BIT_WIDE, description="Write Command ready")
        self.aw_addr = CSRStorage(
            axi_port.address_width, description="Write Command address"
        )

        # Write
        self.w_valid = CSRStorage(ONE_BIT_WIDE, description="Write valid")
        self.w_ready = CSRStatus(ONE_BIT_WIDE, description="Write ready")
        self.w_data = CSRStorage(axi_port.data_width, description="Write data")
        self.w_strb = CSRStorage(
            axi_port.data_width // 8,
            description="Write strobe: Indicates the byte lanes that hold valid data",
        )

        # Write response
        self.b_valid = CSRStatus(ONE_BIT_WIDE, description="Write response valid")
        self.b_ready = CSRStorage(ONE_BIT_WIDE, description="Write response ready")
        self.b_resp = CSRStatus(
            2,
            description="Write response: This indicates the status of the write transaction",
        )

        # Read command
        self.ar_valid = CSRStorage(ONE_BIT_WIDE, description="Read Command valid")
        self.ar_ready = CSRStatus(ONE_BIT_WIDE, description="Read Command ready")
        self.ar_addr = CSRStorage(
            axi_port.address_width, description="Read Command address"
        )

        # Read
        self.r_valid = CSRStatus(ONE_BIT_WIDE, description="Read valid")
        self.r_ready = CSRStorage(ONE_BIT_WIDE, description="Read ready")
        self.r_data = CSRStatus(axi_port.data_width, description="Read data")
        self.r_resp = CSRStatus(
            2, description="Read response: Indicates the status of the read response"
        )

        # All other variables for HBM controller are set to default values here, as in AXILite2AXI

        burst_type = "INCR"  # Comment in AXILite2AXI says the following:

        # Burst type has no meaning as we use burst length of 1, but AXI slaves may require certain
        # type of bursts, so it is probably safest to use INCR in general.

        burst_type = {
            "FIXED": 0b00,
            "INCR": 0b01,
            "WRAP": 0b10,
        }[burst_type]

        burst_size = log2_int(axi_port.data_width // 8)

        # Comment from AXILiteInterface:
        # present for interconnect with other cores but not used by LiteX.
        prot = 0

        # Write command I/O's
        # Set with variables
        axi_port.aw.valid.eq(self.aw_valid.storage)
        self.aw_ready.status.eq(axi_port.aw.ready)
        axi_port.aw.addr.eq(self.aw_addr.storage)

        # Set with default values
        axi_port.aw.burst.eq(burst_type)
        axi_port.aw.len.eq(0)  # 1 transfer per burst
        axi_port.aw.size.eq(burst_size)
        axi_port.aw.lock.eq(0)  # Normal access
        axi_port.aw.prot.eq(prot)
        axi_port.aw.cache.eq(0b0011)  # Normal Non-cacheable Bufferable
        axi_port.aw.qos.eq(
            0
        )  # (Quality of Service) Identifier sent for each write transaction
        axi_port.aw.id.eq(0)  #

        # Write I/O's
        # Set with variables
        axi_port.w.valid.eq(self.w_valid.storage)
        self.w_ready.status.eq(axi_port.w.ready)
        axi_port.w.data.eq(self.w_data.storage)
        axi_port.w.strb.eq(self.w_strb.storage)

        # Set with default values
        axi_port.w.last.eq(1)  # Signal indicates last transfer in a write burst

        # Write response I/O's
        # Set with variables
        self.b_valid.status.eq(axi_port.b.valid)
        axi_port.b.ready.eq(self.b_ready.storage)
        self.b_resp.status.eq(axi_port.b.resp)

        # Read command I/O's
        # Set with variables
        axi_port.ar.valid.eq(self.ar_valid.storage)
        self.ar_ready.status.eq(axi_port.ar.ready)
        axi_port.ar.addr.eq(self.ar_addr.storage)

        # Set with default values
        axi_port.ar.burst.eq(burst_type)
        axi_port.ar.len.eq(0)  # 1 transfer per bit
        axi_port.ar.size.eq(burst_size)
        axi_port.ar.lock.eq(0)  # Normal access
        axi_port.ar.prot.eq(prot)
        axi_port.ar.cache.eq(0b0011)  # Normal Non-cacheable Bufferable
        axi_port.ar.qos.eq(0)
        axi_port.ar.id.eq(0)

        # Read I/O's
        # Set with variables
        self.r_valid.status.eq(axi_port.r.valid)
        axi_port.r.ready.eq(self.r_ready.storage)
        self.r_data.status.eq(axi_port.r.data)
        self.r_resp.status.eq(axi_port.r.resp)

from litex.soc.interconnect.axi.axi_lite import AXILiteInterface

# class HBMAXILiteFunctionsAttempt(Module, AutoCSR):
#     """
#     Use the read and write commands in AxiLite to access hbm
#     """

#     def __init__(self, axi_port):

#         self.address = CSRStorage(28, description="Rightmost 28 bits of hbm address, will be shifted by 5")
#         self.data = CSRStorage(32, description="32 bits of data (max storage of csrstorage)")
#         self.perform_write = CSRStorage(ONE_BIT_WIDE, description="Start performing a write")
#         self.perform_read = CSRStorage(ONE_BIT_WIDE, description="Start to perform a read")
#         self.error_occured = CSRStatus(ONE_BIT_WIDE, description="Error occured")

#         # Check that the object is the class we are expecting.
#         if (isinstance(axi_port, AXILiteInterface) == False):
#             self.error_occured.eq(1)
#             return

#         hbm_lite_fsm = FSM(reset_state="WAIT_INSTRUCTION")
#         self.submodules.hbm_lite_fsm = hbm_lite_fsm

#         hbm_lite_fsm.act(
#             "WAIT_INSTRUCTION",

#         )

