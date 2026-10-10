const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const os = require("node:os");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { once } = require("node:events");

async function main() {
  const root = path.resolve(__dirname, "../_site");
  const expectsBeta = Boolean(JSON.parse(fs.readFileSync(path.join(root, "releases/installer-beta.json")))?.tag_name);
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), "beta-layout-"));
  const server = http.createServer((req, res) => {
    const pathname = new URL(req.url, "http://localhost").pathname;
    const file = path.join(root, pathname.endsWith("/") ? `${pathname}index.html` : pathname);
    if (!file.startsWith(`${root}/`)) { res.writeHead(403).end(); return; }
    fs.readFile(file, (error, data) => {
      if (error) { res.writeHead(404).end(); return; }
      if (file.endsWith('.html')) res.setHeader('Content-Type', 'text/html; charset=utf-8');
      if (file.endsWith('.js')) res.setHeader('Content-Type', 'application/javascript');
      res.end(data);
    });
  });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const browser = spawn(process.env.CHROME || "google-chrome", [
    "--headless", "--no-sandbox", "--disable-gpu", "--remote-debugging-pipe",
    `--user-data-dir=${profile}`, "about:blank",
  ], { stdio: ["ignore", "ignore", "pipe", "pipe", "pipe"] });
  let stderr = "";
  browser.stderr.on("data", chunk => { stderr = (stderr + chunk).slice(-4000); });
  let sequence = 0;
  let buffer = "";
  const pending = new Map();
  const loads = new Map();
  browser.stdio[3].on("error", () => {});
  browser.stdio[4].on("data", chunk => {
    buffer += chunk.toString();
    let end;
    while ((end = buffer.indexOf("\0")) !== -1) {
      const message = JSON.parse(buffer.slice(0, end));
      buffer = buffer.slice(end + 1);
      if (message.method === 'Page.loadEventFired') loads.get(message.sessionId)?.();
      const request = pending.get(message.id);
      if (!request) continue;
      pending.delete(message.id);
      clearTimeout(request.timer);
      if (message.error) request.reject(new Error(message.error.message));
      else request.resolve(message.result);
    }
  });
  browser.on("error", error => {
    for (const request of pending.values()) { clearTimeout(request.timer); request.reject(error); }
    pending.clear();
  });
  function send(method, params = {}, sessionId) {
    return new Promise((resolve, reject) => {
      const id = ++sequence;
      const timer = setTimeout(() => { pending.delete(id); reject(new Error(`Chrome timed out: ${method}\n${stderr}`)); }, 30000);
      pending.set(id, { resolve, reject, timer });
      browser.stdio[3].write(JSON.stringify({ id, method, params, sessionId }) + "\0");
    });
  }
  try {
    for (const language of ["", "en/"]) {
      for (const width of [320, 390, 1280]) {
        const { targetId } = await send("Target.createTarget", { url: "about:blank" });
        const { sessionId } = await send("Target.attachToTarget", { targetId, flatten: true });
        await send("Emulation.setDeviceMetricsOverride", { width, height: 1000, deviceScaleFactor: 1, mobile: width < 768 }, sessionId);
        await send('Page.enable', {}, sessionId);
        const loaded = new Promise((resolve, reject) => {
          const timer = setTimeout(() => reject(new Error('Page load timed out')), 30000);
          loads.set(sessionId, () => { clearTimeout(timer); loads.delete(sessionId); resolve(); });
        });
        await send("Page.navigate", { url: `http://127.0.0.1:${server.address().port}/${language}` }, sessionId);
        await loaded;
        const { result, exceptionDetails } = await send("Runtime.evaluate", {
          expression: `(async () => {
            while (document.readyState !== 'complete') await new Promise(resolve => setTimeout(resolve, 50));
            await document.fonts.ready;
            const card = document.querySelector('.installer-beta');
            if (!card) return { absent: true };
            card.open = true;
            card.scrollIntoView({ block: 'center', behavior: 'instant' });
            await new Promise(requestAnimationFrame);
            const box = card.getBoundingClientRect();
            const stable = card.previousElementSibling;
            const list = card.querySelector('ul');
            const listBox = list.getBoundingClientRect();
            return {
              width: innerWidth,
              overflow: document.documentElement.scrollWidth - innerWidth,
              afterStable: stable.matches('p.installer-meta') && stable.getBoundingClientRect().bottom <= box.top,
              contained: [...card.querySelectorAll('li, a')].every(node => {
                const bounds = node.getBoundingClientRect();
                return bounds.width > 0 && bounds.left >= box.left && bounds.right <= box.right;
              }),
              markersInside: [...list.children].every(node => node.getBoundingClientRect().left - parseFloat(getComputedStyle(node).fontSize) >= listBox.left),
            };
          })()`,
          awaitPromise: true, returnByValue: true,
        }, sessionId);
        assert.equal(exceptionDetails, undefined, JSON.stringify(exceptionDetails));
        assert.equal(Boolean(result.value.absent), !expectsBeta, 'Beta visibility must match the generated manifest');
        if (!result.value.absent) {
          assert.equal(result.value.width, width);
          assert.ok(result.value.overflow <= 1, JSON.stringify(result.value));
          assert.ok(result.value.afterStable, "Beta must appear below stable release notes");
          assert.ok(result.value.contained, "Beta links must fit inside the card");
          assert.ok(result.value.markersInside, "List markers must fit inside their list");
          if (process.env.SCREENSHOT_DIR) {
            fs.mkdirSync(process.env.SCREENSHOT_DIR, { recursive: true });
            const screenshot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false }, sessionId);
            fs.writeFileSync(path.join(process.env.SCREENSHOT_DIR, `${language ? 'en' : 'de'}-${width}.png`), Buffer.from(screenshot.data, "base64"));
          }
        }
        console.log(`OK: ${language || 'de'} at ${width}px ${JSON.stringify(result.value)}`);
        await send("Target.closeTarget", { targetId });
      }
    }
  } finally {
    const exited = once(browser, "close");
    browser.kill();
    await exited;
    await new Promise(resolve => server.close(resolve));
    fs.rmSync(profile, { recursive: true, force: true });
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
