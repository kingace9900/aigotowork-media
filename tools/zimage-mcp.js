#!/usr/bin/env node
// zimage-mcp.js — 本機 Z-Image Turbo 生圖 MCP（給 Claude 桌面版用）
// 直接呼叫 Open Generative AI 已下載好的 sd-cli.exe 與模型，不用開 App、不用控制畫面。
// 不需要 npm 套件，只要 Node.js。輸出存到 %USERPROFILE%\Pictures\aigotowork\
'use strict';
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');
const readline = require('readline');

const APPDATA = process.env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming');
const LOCAL_AI = process.env.OPEN_GENERATIVE_AI_LOCAL_AI_DIR || path.join(APPDATA, 'open-generative-ai', 'local-ai');
const BIN = path.join(LOCAL_AI, 'bin', process.platform === 'win32' ? 'sd-cli.exe' : 'sd-cli');
const MODELS = path.join(LOCAL_AI, 'models');
const MODEL = path.join(MODELS, 'z_image_turbo-Q4_K.gguf');
const LLM = path.join(MODELS, 'Qwen3-4B-Instruct-2507-UD-Q4_K_XL.gguf');
const VAE = path.join(MODELS, 'ae.safetensors');
const OUT_DIR = process.env.ZIMAGE_OUT_DIR || path.join(os.homedir(), 'Pictures', 'aigotowork');

const SIZES = { '1:1': [1024, 1024], '3:4': [768, 1024], '4:3': [1024, 768], '16:9': [1344, 768], '9:16': [768, 1344] };
const NO_TEXT = ' No text, no letters, no words, no logo, no watermark.';

function send(msg) { process.stdout.write(JSON.stringify(msg) + '\n'); }
function log(...a) { process.stderr.write('[zimage-mcp] ' + a.join(' ') + '\n'); }

function checkFiles() {
  const missing = [BIN, MODEL, LLM, VAE].filter(p => !fs.existsSync(p));
  return missing;
}

function runSd(args) {
  return new Promise((resolve, reject) => {
    const p = spawn(BIN, args, { cwd: path.dirname(BIN), windowsHide: true });
    let tail = '';
    const keep = d => { tail = (tail + d.toString()).slice(-4000); };
    p.stdout.on('data', keep); p.stderr.on('data', keep);
    p.on('error', reject);
    p.on('close', code => code === 0 ? resolve(tail) : reject(new Error(`sd-cli 結束代碼 ${code}\n${tail.slice(-1500)}`)));
  });
}

function makePreview(png, jpg) {
  // 用 Windows 內建的 System.Drawing 縮成 512px 寬的 JPEG 預覽；失敗就略過
  return new Promise(resolve => {
    if (process.platform !== 'win32') return resolve(false);
    const ps = `Add-Type -AssemblyName System.Drawing; $i=[Drawing.Image]::FromFile('${png}'); $w=512; $h=[int]($i.Height*$w/$i.Width); $b=New-Object Drawing.Bitmap $i,$w,$h; $b.Save('${jpg}',[Drawing.Imaging.ImageFormat]::Jpeg); $b.Dispose(); $i.Dispose()`;
    const p = spawn('powershell.exe', ['-NoProfile', '-Command', ps], { windowsHide: true });
    p.on('close', c => resolve(c === 0 && fs.existsSync(jpg)));
    p.on('error', () => resolve(false));
  });
}

async function generate(a) {
  const missing = checkFiles();
  if (missing.length) throw new Error('找不到這些檔案（請先在 Open Generative AI 的 Local Models 下載 Z-Image Turbo 全部元件）：\n' + missing.join('\n'));
  const [w, h] = SIZES[a.aspect_ratio || '1:1'] || SIZES['1:1'];
  const seed = Number.isInteger(a.seed) && a.seed >= 0 ? a.seed : Math.floor(Math.random() * 2147483647);
  fs.mkdirSync(OUT_DIR, { recursive: true });
  const base = (a.name || 'img').replace(/[^\w\-]+/g, '_').slice(0, 40) + '-' + new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19) + '-s' + seed;
  const png = path.join(OUT_DIR, base + '.png');
  const prompt = a.prompt + (a.no_text === false ? '' : NO_TEXT);
  const args = ['--diffusion-model', MODEL, '-p', prompt, '-o', png, '--steps', String(a.steps || 8),
    '-H', String(h), '-W', String(w), '--cfg-scale', '1.0', '--seed', String(seed),
    '--sampling-method', 'euler', '--llm', LLM, '--vae', VAE, '--scheduler', 'simple'];
  if (a.negative_prompt) args.push('-n', a.negative_prompt);
  const t0 = Date.now();
  await runSd(args);
  const secs = ((Date.now() - t0) / 1000).toFixed(0);
  const content = [{ type: 'text', text: `完成：${png}\n尺寸 ${w}x${h}｜seed ${seed}｜耗時 ${secs} 秒\n（同一個 seed＋同一段提示詞會得到同一張圖）` }];
  if (a.preview !== false) {
    const jpg = png.replace(/\.png$/, '-preview.jpg');
    if (await makePreview(png, jpg)) {
      content.push({ type: 'image', data: fs.readFileSync(jpg).toString('base64'), mimeType: 'image/jpeg' });
      fs.unlinkSync(jpg);
    }
  }
  return content;
}

const TOOLS = [{
  name: 'zimage_generate',
  description: '用這台電腦的 Z-Image Turbo（RTX 本機、免費）產生一張圖，存到 %USERPROFILE%\\Pictures\\aigotowork\\，並回傳 512px 預覽。一張約 70–90 秒，一次只能跑一張。',
  inputSchema: {
    type: 'object',
    properties: {
      prompt: { type: 'string', description: '英文提示詞效果最好' },
      aspect_ratio: { type: 'string', enum: Object.keys(SIZES), default: '1:1' },
      seed: { type: 'integer', description: '固定 seed 可重現同一張圖；省略為隨機' },
      name: { type: 'string', description: '檔名前綴，例如 host-pose-a' },
      negative_prompt: { type: 'string' },
      steps: { type: 'integer', default: 8 },
      no_text: { type: 'boolean', default: true, description: '自動在提示詞結尾加上「不要文字」' },
      preview: { type: 'boolean', default: true }
    },
    required: ['prompt']
  }
}, {
  name: 'zimage_status',
  description: '檢查 sd-cli 與 Z-Image 模型檔是否都在，並列出最近產生的圖。',
  inputSchema: { type: 'object', properties: {} }
}];

let busy = false;
async function handle(msg) {
  const { id, method, params } = msg;
  if (method === 'initialize') {
    return send({ jsonrpc: '2.0', id, result: { protocolVersion: params?.protocolVersion || '2024-11-05', capabilities: { tools: {} }, serverInfo: { name: 'zimage-local', version: '1.0.0' } } });
  }
  if (method === 'notifications/initialized' || id === undefined) return;
  if (method === 'ping') return send({ jsonrpc: '2.0', id, result: {} });
  if (method === 'tools/list') return send({ jsonrpc: '2.0', id, result: { tools: TOOLS } });
  if (method === 'tools/call') {
    const name = params?.name, a = params?.arguments || {};
    try {
      if (name === 'zimage_status') {
        const missing = checkFiles();
        let recent = [];
        if (fs.existsSync(OUT_DIR)) recent = fs.readdirSync(OUT_DIR).filter(f => f.endsWith('.png')).sort().slice(-10);
        return send({ jsonrpc: '2.0', id, result: { content: [{ type: 'text', text: (missing.length ? '缺少：\n' + missing.join('\n') : '全部就緒') + `\n輸出資料夾：${OUT_DIR}\n最近：\n${recent.join('\n') || '（無）'}` }] } });
      }
      if (name === 'zimage_generate') {
        if (!a.prompt) throw new Error('需要 prompt');
        if (busy) throw new Error('上一張還在產生中，請等它完成再呼叫');
        busy = true;
        try { return send({ jsonrpc: '2.0', id, result: { content: await generate(a) } }); }
        finally { busy = false; }
      }
      throw new Error('未知工具 ' + name);
    } catch (e) {
      return send({ jsonrpc: '2.0', id, result: { isError: true, content: [{ type: 'text', text: String(e.message || e) }] } });
    }
  }
  send({ jsonrpc: '2.0', id, error: { code: -32601, message: 'Method not found: ' + method } });
}

readline.createInterface({ input: process.stdin }).on('line', line => {
  if (!line.trim()) return;
  let msg; try { msg = JSON.parse(line); } catch { return log('bad json'); }
  handle(msg).catch(e => log(e.stack || e));
});
log('ready; models at', MODELS);
