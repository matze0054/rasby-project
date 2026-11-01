"""Driver for the Waveshare 7.5" e-paper HAT (V2, 800x480, black/white).

The command sequences are taken from Waveshare's epd7in5_V2.py. Pins and SPI device are
parameters; the defaults are the pins of the HAT when it is stacked on the Pi's 40-pin header
(SPI0.0, RST=GPIO17, DC=GPIO25, BUSY=GPIO24, PWR=GPIO18).
"""
import time

WIDTH = 800
HEIGHT = 480
BYTES_PER_ROW = WIDTH // 8
_INVERT = bytes(range(255, -1, -1))  # byte translation table: flips every bit


class EPD:
    width = WIDTH
    height = HEIGHT

    def __init__(self, rst=17, dc=25, busy=24, pwr=18, spi_bus=0, spi_device=0, speed_hz=4_000_000):
        self._pins = (rst, dc, busy, pwr)
        self._spi_args = (spi_bus, spi_device, speed_hz)
        self._spi = None
        self._rst = self._dc = self._busy = self._pwr = None

    # -- low level ---------------------------------------------------------------------

    def _open(self):
        if self._spi is not None:
            return
        import gpiozero
        import spidev

        rst, dc, busy, pwr = self._pins
        bus, device, speed_hz = self._spi_args
        self._rst = gpiozero.LED(rst)
        self._dc = gpiozero.LED(dc)
        self._busy = gpiozero.Button(busy, pull_up=False)
        self._pwr = gpiozero.LED(pwr) if pwr is not None else None
        if self._pwr:
            self._pwr.on()  # powers the panel on HATs with a power switch (Rev2.3)
        self._spi = spidev.SpiDev()
        self._spi.open(bus, device)
        self._spi.max_speed_hz = speed_hz
        self._spi.mode = 0b00

    def _close(self):
        if self._spi is None:
            return
        self._spi.close()
        self._rst.off()
        self._dc.off()
        if self._pwr:
            self._pwr.off()
        for dev in (self._rst, self._dc, self._busy, self._pwr):
            if dev:
                dev.close()
        self._spi = self._rst = self._dc = self._busy = self._pwr = None

    def _command(self, command):
        self._dc.off()
        self._spi.writebytes([command])

    def _data(self, *values):
        self._dc.on()
        self._spi.writebytes(list(values))

    def _data_bulk(self, data):
        self._dc.on()
        self._spi.writebytes2(data)

    def _reset(self):
        self._rst.on()
        time.sleep(0.02)
        self._rst.off()
        time.sleep(0.002)
        self._rst.on()
        time.sleep(0.02)

    def _wait_busy(self):
        # The controller reports status after command 0x71: BUSY is low while it is working.
        self._command(0x71)
        while not self._busy.value:
            time.sleep(0.005)
            self._command(0x71)
        time.sleep(0.02)

    def _power_on(self):
        self._command(0x04)
        time.sleep(0.1)
        self._wait_busy()

    # -- init variants -----------------------------------------------------------------

    def init(self):
        """Full-refresh mode: slowest (about 4 s), flashes, but resets ghosting."""
        self._open()
        self._reset()
        self._command(0x06)  # booster soft start
        self._data(0x17, 0x17, 0x28, 0x17)
        self._command(0x01)  # power setting
        self._data(0x07, 0x07, 0x28, 0x17)
        self._power_on()
        self._command(0x00)  # panel setting
        self._data(0x1F)
        self._command(0x61)  # resolution 800x480
        self._data(0x03, 0x20, 0x01, 0xE0)
        self._command(0x15)
        self._data(0x00)
        self._command(0x50)  # VCOM and data interval
        self._data(0x10, 0x07)
        self._command(0x60)  # TCON setting
        self._data(0x22)

    def init_fast(self):
        """Fast full-frame refresh (about 1.5 s)."""
        self._open()
        self._reset()
        self._command(0x00)
        self._data(0x1F)
        self._command(0x50)
        self._data(0x10, 0x07)
        self._power_on()
        self._command(0x06)
        self._data(0x27, 0x27, 0x18, 0x17)
        self._command(0xE0)
        self._data(0x02)
        self._command(0xE5)
        self._data(0x5A)

    def init_part(self):
        """Partial-refresh mode (about 0.5 s, no flash); use with display_partial()."""
        self._open()
        self._reset()
        self._command(0x00)
        self._data(0x1F)
        self._power_on()
        self._command(0xE0)
        self._data(0x02)
        self._command(0xE5)
        self._data(0x6E)

    # -- drawing -----------------------------------------------------------------------

    def getbuffer(self, image):
        """Convert a PIL image (800x480, or 480x800 which is rotated) to the panel format."""
        if image.size == (HEIGHT, WIDTH):
            image = image.rotate(90, expand=True)
        if image.size != (WIDTH, HEIGHT):
            raise ValueError(f"image must be {WIDTH}x{HEIGHT}, got {image.width}x{image.height}")
        # PIL: 1 = white. The controller wants 1 = black.
        return bytes(image.convert("1").tobytes("raw")).translate(_INVERT)

    def display(self, buf):
        """Write a frame and refresh with whichever init*() mode was selected last."""
        self._command(0x10)
        self._data_bulk(buf.translate(_INVERT))
        self._command(0x13)
        self._data_bulk(buf)
        self._refresh()

    def display_partial(self, buf, x0=0, y0=0, x1=WIDTH, y1=HEIGHT):
        """Update only a window of the frame. Call init_part() first. `buf` is a full frame."""
        x0, x1 = x0 // 8 * 8, -(-x1 // 8) * 8  # the window must be byte-aligned horizontally
        window = b"".join(
            buf[y * BYTES_PER_ROW + x0 // 8 : y * BYTES_PER_ROW + x1 // 8] for y in range(y0, y1)
        )
        self._command(0x50)
        self._data(0xA9, 0x07)
        self._command(0x91)  # enter partial mode
        self._command(0x90)  # window
        self._data(x0 >> 8, x0 & 0xFF, (x1 - 1) >> 8, (x1 - 1) & 0xFF)
        self._data(y0 >> 8, y0 & 0xFF, (y1 - 1) >> 8, (y1 - 1) & 0xFF, 0x01)
        self._command(0x13)
        self._data_bulk(window.translate(_INVERT))  # polarity is inverted in partial mode
        self._refresh()

    def clear(self):
        """Turn the whole panel white (call after init())."""
        blank = bytes(BYTES_PER_ROW * HEIGHT)
        self._command(0x10)
        self._data_bulk(blank.translate(_INVERT))
        self._command(0x13)
        self._data_bulk(blank)
        self._refresh()

    def _refresh(self):
        self._command(0x12)
        time.sleep(0.1)
        self._wait_busy()

    def sleep(self):
        """Power the panel down and release SPI/GPIO. init*() reopens them."""
        if self._spi is None:
            return
        self._command(0x50)
        self._data(0xF7)
        self._command(0x02)  # power off
        self._wait_busy()
        self._command(0x07)  # deep sleep
        self._data(0xA5)
        time.sleep(2)
        self._close()

