// OCR of every page image in a folder with Apple Vision's document reader (macOS 26 or later),
// which keeps the reading order of columns and boxes. Writes <page>.txt next to each <page>.png.
// Built and run by pdf_transcribe.py.
import Foundation
import Vision

let folder = URL(fileURLWithPath: CommandLine.arguments[1])
let images = try FileManager.default.contentsOfDirectory(at: folder, includingPropertiesForKeys: nil)
  .filter { $0.pathExtension == "png" }

var request = RecognizeDocumentsRequest()
// A PDF can come in any language.
request.textRecognitionOptions.automaticallyDetectLanguage = true

for url in images {
  let observations = try await request.perform(on: url)
  let text = observations.map(\.document.text.transcript).joined(separator: "\n")
  try text.write(to: url.deletingPathExtension().appendingPathExtension("txt"), atomically: true, encoding: .utf8)
}
