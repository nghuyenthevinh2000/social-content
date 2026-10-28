import { ElevenLabsClient } from "@elevenlabs/elevenlabs-js";
import { createReadStream, createWriteStream, existsSync, mkdirSync } from "fs";
import { Readable } from "stream";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ugcVideoDir = path.resolve(__dirname, "..");
const audioDir = path.join(ugcVideoDir, "assets", "audio");
const voiceSamplePath = path.join(audioDir, "actor_voice.wav");

// The SDK automatically loads ELEVENLABS_API_KEY from .env
const client = new ElevenLabsClient();

export async function getOrCreateVoice(voiceName = "Artisan Workshop Presenter") {
  if (!existsSync(voiceSamplePath)) {
    throw new Error(`Voice sample not found at: ${voiceSamplePath}`);
  }

  console.log(`Checking existing voices for: "${voiceName}"...`);
  const response = await client.voices.getAll();
  const existing = response.voices.find(v => v.name.toLowerCase().includes(voiceName.toLowerCase()) || v.name.toLowerCase().includes("artisan") || v.category === "cloned");
  if (existing) {
    console.log(`Found voice: "${existing.name}" (ID: ${existing.voiceId})`);
    return existing.voiceId;
  }

  console.log(`Cloning voice from ${voiceSamplePath} via ElevenLabs Instant Voice Cloning (IVC)...`);
  try {
    const newVoice = await client.voices.ivc.create({
      name: voiceName,
      description: "Vietnamese artisan workshop presenter for specialty paper and printing",
      files: [createReadStream(voiceSamplePath)],
      removeBackgroundNoise: false,
    });
    console.log(`Voice cloned successfully! Voice ID: ${newVoice.voiceId}`);
    return newVoice.voiceId;
  } catch (err) {
    if (err?.body?.detail?.status === "missing_permissions") {
      console.warn("\n[PERMISSION NOTICE]");
      console.warn("The current API key does not have 'voices_write' enabled.");
      console.warn("Your Starter plan HAS Instant Voice Cloning enabled (canUseInstantVoiceCloning: true).");
      console.warn("You can either:");
      console.warn(" 1. Enable 'Voices: Write' on your API key at: https://elevenlabs.io/app/settings/api-keys");
      console.warn(" 2. OR upload actor_voice.wav directly at: https://elevenlabs.io/app/voice-lab");
      console.warn("Falling back to pre-made expressive Vietnamese voice for preview...\n");
      // Fallback to high quality pre-made voice (Sarah)
      return "EXAVITQu4vr4xnSDxMaL";
    }
    throw err;
  }
}

export async function generateSpeech({
  voiceId,
  text,
  outputPath = path.join(audioDir, "elevenlabs_cloned_speech.mp3"),
  modelId = "eleven_multilingual_v2"
}) {
  console.log(`Generating Vietnamese speech using model: ${modelId}...`);
  console.log(`Voice ID: ${voiceId}`);
  console.log(`Script: "${text}"\n`);

  const audioStream = await client.textToSpeech.convert(voiceId, {
    text,
    modelId,
    voiceSettings: {
      stability: 0.5,
      similarityBoost: 0.8,
      style: 0.0,
      useSpeakerBoost: true,
    }
  });

  mkdirSync(path.dirname(outputPath), { recursive: true });
  await new Promise((resolve, reject) => {
    const fileStream = createWriteStream(outputPath);
    Readable.fromWeb(audioStream)
      .pipe(fileStream)
      .on("finish", resolve)
      .on("error", reject);
  });

  console.log(`Speech successfully written to: ${outputPath}`);
  return outputPath;
}

export async function main() {
  const customSpeech = 
    "Xưởng sản xuất chúng tôi chuyên sản xuất các dòng giấy mỹ thuật cao cấp: giấy ánh kim, giấy Ivory và giấy đỏ nhung. " +
    "Ngoài ra, bên xưởng chúng tôi cung cấp giải pháp mực in chuyên dụng chất lượng cao cho in ấn bao bì và thùng carton. " +
    "Quý khách hàng và đối tác cần tư vấn đặt hàng hoặc nhận mẫu giấy, xin vui lòng liên hệ với xưởng chúng tôi để được hỗ trợ tốt nhất. Xin chân thành cảm ơn!";

  const voiceId = await getOrCreateVoice("Artisan Workshop Presenter");
  const outputPath = path.join(audioDir, "elevenlabs_cloned_speech.mp3");
  await generateSpeech({ voiceId, text: customSpeech, outputPath });
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main().catch((err) => {
    console.error("Error executing voice cloning pipeline:", err);
    process.exit(1);
  });
}
