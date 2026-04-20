import sharp from 'sharp';

/** Creates a flat-color JPEG buffer for use in unit tests (no file I/O). */
export async function makeJpegBuffer(
  width = 512,
  height = 512,
  rgb: [number, number, number] = [200, 40, 40],
): Promise<Buffer> {
  return sharp({
    create: {
      width,
      height,
      channels: 3,
      background: { r: rgb[0], g: rgb[1], b: rgb[2] },
    },
  })
    .jpeg({ quality: 85 })
    .toBuffer();
}
