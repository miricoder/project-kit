/**
 * The preview's PNG export: draw the post's SVG on a 1080 x 1350 canvas and hand the PNG to
 * the claude.ai page's download prompt (a page there cannot start a download itself).
 */
export async function savePostPng(svgUrl: string, filename: string): Promise<string> {
  const img = new window.Image();
  img.src = svgUrl;
  await img.decode();
  const canvas = document.createElement('canvas');
  canvas.width = 1080;
  canvas.height = 1350;
  canvas.getContext('2d')!.drawImage(img, 0, 0, 1080, 1350);
  const png = await new Promise<Blob>((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('The image could not be drawn'))), 'image/png'),
  );
  const w = globalThis as unknown as { claude?: { use(name: string): Promise<any> } };
  const downloads = w.claude?.use ? await w.claude.use('downloads').catch(() => null) : null;
  if (!downloads) return 'Downloading needs the page open on claude.ai.';
  try {
    const r = await downloads.save({ filename, data: png });
    return r?.status === 'saved' ? 'Saved.' : 'Sent.';
  } catch (e) {
    const code = (e as { code?: string }).code;
    return code === 'declined' ? 'Not saved.' : `Not saved: ${(e as Error).message}`;
  }
}
