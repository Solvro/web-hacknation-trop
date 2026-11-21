/**
 * Remotion CLI defaults for the TROP demo renders.
 * Responsibility: codec and quality shared by `studio` and every render. CPU only: no
 * WebGL transitions are used, so the default (software) GL is fine.
 * Idempotency: n/a — pure configuration.
 */
import { Config } from '@remotion/cli/config';

Config.setVideoImageFormat('jpeg');
Config.setJpegQuality(92);
Config.setCodec('h264');
Config.setCrf(20);
Config.setOverwriteOutput(true);
