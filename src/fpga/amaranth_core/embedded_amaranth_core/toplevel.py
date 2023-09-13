from amaranth import *
from amaranth.lib import wiring, data
from amaranth.lib.wiring import In, Out


class PixelClockDiv(wiring.Component):
    clk90   : Out(1) # Pixel clock, 90 deg trailing
    clk     : Out(1) # Pixel clock
    stb     : Out(1) # Single cycle strobe at rising edge of `clk`

    def __init__(self, ratio=2):
        super().__init__()

        assert ratio >= 4 and ratio % 4 == 0, "Ratio must be at least 4 and divisible by 4"
        self.ratio = ratio

    def elaborate(self, platform):
        m = Module()

        # clk90  __/¯¯¯\_
        # clk    /¯¯¯\___
        # rgb    X--------

        clk_reg = Signal(self.ratio, reset=((1 << (self.ratio // 2)) - 1) << (self.ratio // 2))
        m.d.sync += clk_reg.eq(clk_reg.rotate_left(1))
        m.d.comb += [
            self.clk.eq(clk_reg[0]),
            self.clk90.eq(clk_reg[self.ratio // 4]),
        ]

        stb_reg = Signal(self.ratio, reset=1)
        m.d.sync += stb_reg.eq(stb_reg.rotate_left(1))
        m.d.comb += [
            self.stb.eq(stb_reg[0])
        ]

        return m


class Toplevel(wiring.Component):
    clk             : In(1)
    rst             : In(1)
    init_done       : Out(1)

    user1           : Out(1)
    user2           : In(1)

    dbg_tx          : Out(1)
    dbg_rx          : In(1)

    video_rgb_clk   : Out(1)
    video_rgb_clk90 : Out(1)
    video_rgb       : Out(data.StructLayout({"b": 8, "g": 8, "r": 8}))
    video_de        : Out(1)
    video_skip      : Out(1)
    video_vs        : Out(1)
    video_hs        : Out(1)

    audio_clk       : Out(1) # aka audio_mclk
    audio_sync      : Out(1) # aka audio_lrck
    audio_adc       : In(1)
    audio_dac       : Out(1)

    cont1_key       : In(32)
    cont2_key       : In(32)
    cont3_key       : In(32)
    cont4_key       : In(32)
    cont1_joy       : In(32)
    cont2_joy       : In(32)
    cont3_joy       : In(32)
    cont4_joy       : In(32)
    cont1_trig      : In(16)
    cont2_trig      : In(16)
    cont3_trig      : In(16)
    cont4_trig      : In(16)

    def elaborate(self, platform):
        m = Module()

        m.domains.boot = boot = ClockDomain(reset_less=True)
        m.domains.sync = sync = ClockDomain(async_reset=True)
        m.d.comb += [
            boot.clk.eq(self.clk),
            sync.clk.eq(self.clk),
            sync.rst.eq(self.rst),
        ]

        m.d.boot += self.init_done.eq(1)

        # ------------------------------ user code below this line --------------------------------

        m.submodules.video_clk_div = video_clk_div = PixelClockDiv(ratio=4)
        m.d.comb += [
            self.video_rgb_clk.eq(video_clk_div.clk),
            self.video_rgb_clk90.eq(video_clk_div.clk90),
        ]

        VID_V_BPORCH = 10
        VID_V_ACTIVE = 480
        VID_V_TOTAL  = 495
        VID_H_BPORCH = 10
        VID_H_ACTIVE = 600
        VID_H_TOTAL  = 625

        assert 47 <= (74250000 / 4 / VID_V_TOTAL / VID_H_TOTAL) < 61, "Pixel clock out of range"

        with m.If(video_clk_div.stb):
            x_count = Signal(10)
            y_count = Signal(10)

            m.d.sync += [
                self.video_vs.eq((x_count == 0) & (y_count == 0)),
                # HS must occur at least 3 cycles after VS
                self.video_hs.eq(x_count == 3),
            ]

            m.d.sync += x_count.eq(x_count + 1)
            with m.If(x_count == VID_H_TOTAL - 1):
                m.d.sync += x_count.eq(0)
                m.d.sync += y_count.eq(y_count + 1)
                with m.If(y_count == VID_V_TOTAL - 1):
                    m.d.sync += y_count.eq(0)

            m.d.sync += [
                # inactive screen areas must be black
                self.video_de.eq(0),
                self.video_rgb.eq(0)
            ]

            with m.If((x_count >= VID_H_BPORCH) & (x_count < VID_H_ACTIVE + VID_H_BPORCH)):
                with m.If((y_count >= VID_V_BPORCH) & (y_count < VID_V_ACTIVE + VID_V_BPORCH)):
                    m.d.sync += [
                        self.video_de.eq(1),
                        self.video_rgb.r.eq(0xa0),
                        self.video_rgb.g.eq(0x00),
                        self.video_rgb.b.eq(0x80),
                    ]

        return m


def simulate():
    from amaranth.sim import Simulator

    sim = Simulator(Toplevel())
    sim.add_clock(1/74.25e6)
    with sim.write_vcd("dump.vcd"):
        sim.run_until(10e-3, run_passive=True)


def capture_frame():
    import png
    from amaranth.sim import Simulator

    top = Toplevel()
    def bench():
        rows = []
        while not (yield top.video_vs): yield
        while (yield top.video_vs): yield
        # after negedge of vs
        while True:
            cols = []
            while not (yield top.video_hs): yield
            while not ((yield top.video_vs) or (yield top.video_de)): yield
            if (yield top.video_vs):
                break
            while True:
                while (yield top.video_rgb_clk90): yield
                while not (yield top.video_rgb_clk90): yield
                # at posedge of clk90
                if (yield top.video_de):
                    cols.append((yield top.video_rgb.r))
                    cols.append((yield top.video_rgb.g))
                    cols.append((yield top.video_rgb.b))
                else:
                    break
            print(f"row {len(rows)}: {len(cols) // 3} cols")
            rows.append(cols)
            with open("frame.png", "wb") as file:
                png.Writer(len(rows[0]) // 3, len(rows), greyscale=False).write(file, rows)
        print(f"{len(rows)} rows")

    sim = Simulator(top)
    sim.add_clock(1/74.25e6)
    sim.add_sync_process(bench)
    sim.run()


def generate():
    from pathlib import Path
    from amaranth.back import verilog
    from .platform import IntelPlatform

    toplevel = Toplevel()
    with open(Path(__file__).parent.parent.parent / "core" / "amaranth_core.v", "w") as f:
        f.write(verilog.convert(toplevel, platform=IntelPlatform, name="amaranth_core", strip_internal_attrs=True))
