import { ElevenLabsClient } from "@elevenlabs/elevenlabs-js";
import { writeFileSync } from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(__dirname, "../renders/omni-1.1-flash");
const VOICE_ID = "FXJGVNPXC71BGT9PjlMX"; // Vietnamese Actual Women Voice (vi-northern)

const CLAUSES = [
  "Xưởng ơi, có mẫu giấy in thiệp cưới nào vừa sang vừa kinh tế không?",
  "Dòng Giấy Ánh Kim một trăm tám mươi bên em bề mặt nhũ xà cừ cực mịn, ăn mực sắc nét, lên máy bế hay gấp nếp không lo nứt gãy.",
  "Khổ tiêu chuẩn bảy mươi chín nhân một trăm linh chín luôn sẵn tại kho xưởng,",
  "nhận đơn từ hai gam cho xưởng in test máy.",
  "Đặc biệt lên thiệp in cực kỳ sắc nét.",
  "Nhắn tin xưởng em gửi mẫu miễn phí nhé!",
];

async function main() {
  const client = new ElevenLabsClient();
  const res = await client.textToSpeech.convertWithTimestamps(VOICE_ID, {
    text: CLAUSES.join(" "),
    modelId: "eleven_v3",
    outputFormat: "mp3_44100_192",
    voiceSettings: { stability: 0.5, similarityBoost: 0.85, style: 0.0, useSpeakerBoost: true },
  });

  const rawMp3 = path.join(outDir, "tts_v3_raw.mp3");
  const alignJson = path.join(outDir, "tts_v3_alignment.json");
  writeFileSync(rawMp3, Buffer.from(res.audioBase64, "base64"));
  writeFileSync(alignJson, JSON.stringify(res.alignment, null, 2));
  console.log(`Saved eleven_v3 audio (${rawMp3}) and alignment (${alignJson})`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
