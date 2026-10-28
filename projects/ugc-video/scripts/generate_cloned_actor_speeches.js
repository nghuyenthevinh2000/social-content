import { ElevenLabsClient } from "@elevenlabs/elevenlabs-js";
import { createWriteStream, mkdirSync } from "fs";
import { Readable } from "stream";
import path from "path";
import { fileURLToPath } from "url";
import { execSync } from "child_process";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ugcVideoDir = path.resolve(__dirname, "..");
const audioDir = path.join(ugcVideoDir, "assets", "audio");

const client = new ElevenLabsClient();
const CLONED_VOICE_ID = "4pDfNAFSqZdVnr5Xfufk";

const SCRIPTS = [
  {
    id: "script_1_sample_offer",
    title: "Mẫu giấy tận nơi & Test mực in miễn phí",
    text: "Chào các bạn! Xưởng mình đang có sẵn các dòng giấy ánh kim, giấy Ivory và giấy đỏ nhung mẫu mới nhất. Bên mình nhận gửi mẫu giấy tận xưởng và hỗ trợ test mực in thùng carton miễn phí. Bạn nào cần báo giá sỉ tận gốc, nhắn tin cho xưởng mình ngay nhé!"
  },
  {
    id: "script_2_factory_pitch",
    title: "Nguồn giấy mỹ thuật & Mực in giá tận gốc",
    text: "Bạn đang tìm nguồn giấy mỹ thuật và mực in chất lượng cao giá tận xưởng? Bên mình chuyên sản xuất trực tiếp giấy ánh kim lấp lánh, Ivory dày dặn và đỏ nhung mịn đẹp, hoàn toàn không qua trung gian. Hãy liên hệ với chúng tôi để nhận bảng giá ưu đãi nhất hôm nay!"
  },
  {
    id: "script_3_tiktok_hook",
    title: "Short Hook: In bao lì xì & Hộp quà cao cấp",
    text: "Có ai đang cần giấy ánh kim hay giấy đỏ nhung để in bao lì xì, làm hộp quà Tết và bao bì cao cấp không? Xưởng mình sản xuất số lượng lớn, sẵn hàng giao ngay kèm mực in thùng carton chuyên dụng. Bấm liên hệ để được xưởng tư vấn ngay nhé!"
  }
];

async function generateClip(voiceId, text, baseFilename) {
  console.log(`\nGenerating with Cloned Voice (${voiceId})...`);
  console.log(`Text: "${text}"`);

  const mp3Path = path.join(audioDir, `${baseFilename}.mp3`);
  const wavPath = path.join(audioDir, `${baseFilename}.wav`);

  const audioStream = await client.textToSpeech.convert(voiceId, {
    text,
    modelId: "eleven_multilingual_v2",
    voiceSettings: {
      stability: 0.55,
      similarityBoost: 0.85,
      style: 0.0,
      useSpeakerBoost: true
    }
  });

  mkdirSync(audioDir, { recursive: true });
  await new Promise((resolve, reject) => {
    const fileStream = createWriteStream(mp3Path);
    Readable.fromWeb(audioStream)
      .pipe(fileStream)
      .on("finish", resolve)
      .on("error", reject);
  });

  // Convert to 44.1kHz 16-bit PCM WAV
  execSync(`ffmpeg -hide_banner -y -i "${mp3Path}" -c:a pcm_s16le "${wavPath}"`);
  console.log(`Saved MP3: ${mp3Path}`);
  console.log(`Saved WAV: ${wavPath}`);

  return { mp3Path, wavPath };
}

async function main() {
  console.log("=== Generating Different Scripts with Cloned Actor Voice ===");
  console.log(`Using Cloned Voice ID: ${CLONED_VOICE_ID}`);

  for (const item of SCRIPTS) {
    console.log(`\n--- Script: ${item.title} ---`);
    await generateClip(CLONED_VOICE_ID, item.text, `cloned_actor_${item.id}`);
  }

  // Also update default elevenlabs_cloned_speech.mp3 / .wav with Script 1
  console.log("\nUpdating default elevenlabs_cloned_speech files with cloned actor voice...");
  execSync(`cp "${path.join(audioDir, 'cloned_actor_script_1_sample_offer.mp3')}" "${path.join(audioDir, 'elevenlabs_cloned_speech.mp3')}"`);
  execSync(`cp "${path.join(audioDir, 'cloned_actor_script_1_sample_offer.wav')}" "${path.join(audioDir, 'elevenlabs_cloned_speech.wav')}"`);
  console.log("SUCCESS: All speech files generated using authentic cloned actor voice!");
}

main().catch(err => {
  console.error("Error generating speeches:", err);
  process.exit(1);
});
