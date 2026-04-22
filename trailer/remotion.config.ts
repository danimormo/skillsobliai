import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("jpeg");
Config.setConcurrency(1);
Config.setChromiumOpenGlRenderer("angle");
Config.setChromiumIgnoreCertificateErrors(true);
Config.setChromiumDisableWebSecurity(true);
Config.setBrowserExecutable("/opt/chrome/chrome-headless-shell-linux64/chrome-headless-shell");
