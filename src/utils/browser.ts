import { chromium as chromiumExtra } from 'playwright-extra';
import stealth from 'puppeteer-extra-plugin-stealth';
import type { Browser, BrowserContext, Page } from 'playwright';
import { config } from '../config.js';
import { pickUserAgent } from './userAgents.js';
import { logger } from './logger.js';

let stealthInstalled = false;
function installStealthOnce(): void {
  if (stealthInstalled) return;
  // puppeteer-extra-plugin-stealth is cross-compatible with playwright-extra.
  chromiumExtra.use(stealth());
  stealthInstalled = true;
}

let sharedBrowser: Browser | null = null;

export async function getBrowser(): Promise<Browser> {
  if (sharedBrowser && sharedBrowser.isConnected()) return sharedBrowser;
  installStealthOnce();
  logger.debug({ headless: config.headless }, 'Launching shared Chromium');
  sharedBrowser = await chromiumExtra.launch({
    headless: config.headless,
    args: [
      '--disable-blink-features=AutomationControlled',
      '--no-sandbox',
      '--disable-dev-shm-usage',
    ],
  });
  return sharedBrowser;
}

export interface ContextOptions {
  locale?: string;
  timezoneId?: string;
}

export async function newStealthContext(opts: ContextOptions = {}): Promise<BrowserContext> {
  const browser = await getBrowser();
  const ctx = await browser.newContext({
    userAgent: pickUserAgent(),
    locale: opts.locale ?? 'en-US',
    timezoneId: opts.timezoneId ?? 'Europe/Rome',
    viewport: { width: 1366, height: 768 },
    deviceScaleFactor: 1,
    ...(config.proxyUrl ? { proxy: { server: config.proxyUrl } } : {}),
  });
  ctx.setDefaultTimeout(config.browserTimeoutMs);
  ctx.setDefaultNavigationTimeout(config.browserTimeoutMs);
  return ctx;
}

/** Random human-like delay between two bounds. */
export async function humanDelay(
  min = config.actionDelayMinMs,
  max = config.actionDelayMaxMs,
): Promise<void> {
  const ms = Math.floor(min + Math.random() * Math.max(0, max - min));
  await new Promise((r) => setTimeout(r, ms));
}

/** Heuristic CAPTCHA / anti-bot detection on the current page. */
export async function detectCaptcha(page: Page): Promise<boolean> {
  try {
    const html = (await page.content()).toLowerCase();
    const markers = [
      'recaptcha',
      'g-recaptcha',
      'hcaptcha',
      'cf-challenge',
      'cloudflare',
      'please verify you are a human',
      'slide to verify',
      'px-captcha',
      'geetest',
    ];
    return markers.some((m) => html.includes(m));
  } catch {
    return false;
  }
}

export async function closeBrowser(): Promise<void> {
  if (sharedBrowser) {
    await sharedBrowser.close().catch(() => {});
    sharedBrowser = null;
  }
}
