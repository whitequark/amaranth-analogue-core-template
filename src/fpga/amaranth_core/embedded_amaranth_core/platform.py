from amaranth import *


# Copy of the parts of amaranth/amaranth/vendor/_intel.py that are necessary to have Amaranth
# clock domain crossing primitives (AsyncFIFO, etc) work on an Analogue OpenFPGA device.
class IntelPlatform:
    def get_ff_sync(self, ff_sync):
        return Instance("altera_std_synchronizer_bundle",
            p_width=len(ff_sync.i),
            p_depth=ff_sync._stages,
            i_clk=ClockSignal(ff_sync._o_domain),
            i_reset_n=Const(1),
            i_din=ff_sync.i,
            o_dout=ff_sync.o,
        )

    def get_async_ff_sync(self, async_ff_sync):
        m = Module()
        sync_output = Signal()
        if async_ff_sync._edge == "pos":
            m.submodules += Instance("altera_std_synchronizer",
                p_depth=async_ff_sync._stages,
                i_clk=ClockSignal(async_ff_sync._o_domain),
                i_reset_n=~async_ff_sync.i,
                i_din=Const(1),
                o_dout=sync_output,
            )
        else:
            m.submodules += Instance("altera_std_synchronizer",
                p_depth=async_ff_sync._stages,
                i_clk=ClockSignal(async_ff_sync._o_domain),
                i_reset_n=async_ff_sync.i,
                i_din=Const(1),
                o_dout=sync_output,
            )
        m.d.comb += async_ff_sync.o.eq(~sync_output)
        return m


