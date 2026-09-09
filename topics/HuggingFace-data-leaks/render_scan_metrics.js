/**
 * Truffle Security 7.6 PB AI Training Data Secret Scan Report Generator
 * Renders clear, human-understandable metrics from the research paper/blog post.
 */

const scanData = {
  headline: "Truffle Security Scan of Hugging Face Public AI Training Data",
  metrics: {
    scannedVolumePB: 7.6,
    scannedFiles: 187_000_000,
    affectedDatasets: 6_003,
    liveUniqueSecrets: 221_303,
    maxSinglePiiLeakGB: 393,
    estimatedGlobalPopulationAffectedPercent: 3.7,
    estimatedAffectedPeople: 300_000_000
  },
  accessGrantedBySecrets: [
    {
      systemAccess: "Cloud Storage Buckets",
      description: "Direct read/write access to raw cloud files & backups (AWS S3, Google Cloud Storage)",
      threatLevel: "High"
    },
    {
      systemAccess: "Hosted Production Databases",
      description: "Live connection strings for SQL/Mongo databases holding private customer data",
      threatLevel: "High"
    },
    {
      systemAccess: "Cloud Admin Credentials",
      description: "Full administrative control keys for entire corporate cloud infrastructure",
      threatLevel: "Critical"
    },
    {
      systemAccess: "Software Update Tokens",
      description: "Release tokens capable of pushing malicious code directly into widely installed software",
      threatLevel: "Critical"
    },
    {
      systemAccess: "393 GB PII Database Secret",
      description: "Single key exposing personal information covering ~3.7% of the global population (~300M people)",
      threatLevel: "Extreme"
    }
  ]
};

function formatNumber(num) {
  return new Intl.NumberFormat('en-US').format(num);
}

function renderTerminalReport() {
  const m = scanData.metrics;

  console.log("\n==================================================================================");
  console.log(` 🚀 ${scanData.headline.toUpperCase()}`);
  console.log("==================================================================================\n");

  console.log("📌 OVERALL SCAN SCALE:");
  console.log(` • Data Scanned           : ${m.scannedVolumePB} Petabytes (${formatNumber(m.scannedVolumePB * 1000)} TB)`);
  console.log(` • Total Files Scanned    : ${formatNumber(m.scannedFiles)} files across Hugging Face datasets`);
  console.log(` • Vulnerable Datasets    : ${formatNumber(m.affectedDatasets)} datasets containing active secrets`);
  console.log(` • Active Secrets Found   : ${formatNumber(m.liveUniqueSecrets)} live, usable passwords & API keys`);
  console.log(` • Single Largest Exposure: ${m.maxSinglePiiLeakGB} GB database (~3.7% of world population / ~300M people)\n`);

  console.log("🔓 WHAT THE LEAKED SECRETS GIVE ACCESS TO:");
  console.table(scanData.accessGrantedBySecrets);

  console.log("\n==================================================================================\n");
}

// Execute report if run via Node CLI
if (typeof require !== 'undefined' && require.main === module) {
  renderTerminalReport();
}

// Export for module/browser usage
if (typeof module !== 'undefined') {
  module.exports = { scanData, formatNumber, renderTerminalReport };
}
