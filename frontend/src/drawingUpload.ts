export const maxDrawingBytes = 20 * 1024 * 1024

export async function extractionFile(file: File, provider: 'Claude' | 'OpenAI' | null): Promise<Blob> {
  // Claude caps each base64 image at 10 MB, equivalent to 7.5 MB of raw bytes.
  const inlineLimit = provider === 'Claude' ? 7_500_000 : 8 * 1024 * 1024
  if (file.type === 'application/pdf' || file.size <= inlineLimit) return file

  const { PDFDocument } = await import('pdf-lib')
  const pdf = await PDFDocument.create()
  const bytes = await file.arrayBuffer()
  const image = file.type === 'image/jpeg' ? await pdf.embedJpg(bytes) : await pdf.embedPng(bytes)

  // PDF page dimensions are independent of the embedded image's pixel dimensions.
  const scale = Math.min(1, 1440 / Math.max(image.width, image.height))
  const dimensions = image.scale(scale)
  const page = pdf.addPage([dimensions.width, dimensions.height])
  page.drawImage(image, { x: 0, y: 0, ...dimensions })

  const pdfBytes = await pdf.save()
  if (pdfBytes.byteLength > maxDrawingBytes) {
    throw new Error('The image is too large when embedded in a PDF. Try the original drawing PDF or crop to the one-line at its original resolution.')
  }
  return new Blob([new Uint8Array(pdfBytes)], { type: 'application/pdf' })
}
