#!/usr/bin/env node
"use strict";

const { parseArgs } = require("node:util");
const fs = require("node:fs");
const path = require("node:path");

const MAIN_HELP = `Genesis - Text Learning System (JavaScript port)

Usage:
  genesis.js <command> [options]

Commands:
  train       Train on foundation data
  chat        Interactive conversation
  eval        Run A/B evaluation tests
  test        Test system components
  discover    Discover patterns in text/image/audio
  synthesize  Synthesize from patterns

Run "genesis.js <command> --help" for command-specific options.
`;

const COMMAND_HELP = {
  train: `Usage: genesis.js train [options]

Options:
  --data <dir>                   Foundation data directory
  --output <file>                Output model path (.pkl)
  --use-gpu                      Enable GPU acceleration
  --checkpoint-interval <n>      Save checkpoint every N documents
  --max-documents <n>            Limit documents (for testing)
  --collapse-cosine-threshold <n>    Cosine similarity threshold
  --collapse-harmonic-tolerance <n>  Harmonic tolerance for collapse
  --collapse-octave-tolerance <n>    Octave tolerance for matching
  --enable-collapse              Enable gravitational collapse (default)
  --disable-collapse             Disable gravitational collapse
`,
  chat: `Usage: genesis.js chat [options]

Options:
  --model <file>     Trained model path (.pkl)
  --stream           Stream responses
  --show-stats       Show coherence/state after each response
  --save-on-exit     Save session on exit (default)
`,
  eval: `Usage: genesis.js eval [options]

Options:
  --model <file>        Trained model path (.pkl)
  --test-cases <file>   Test cases JSON file
  --output <file>       Results output path (.json)
`,
  test: `Usage: genesis.js test

Options: none
`,
  discover: `Usage: genesis.js discover [options]

Options:
  --input <file>                    Input file (text/image/audio)
  --output <file>                   Output model path (.pkl)
  --dual-path                       Use dual-path convergence (Gen + Res)
  --modality <text|image|audio>     Input modality (default: text)
  --phase-coherence-threshold <n>   Phase coherence threshold (default: 0.1)
  --link-cross-modal                Enable cross-modal phase-locking
  --collapse-harmonic-tolerance <n> Harmonic tolerance (default: 0.05)
  --collapse-cosine-threshold <n>   Cosine similarity threshold (default: 0.85)
  --collapse-octave-tolerance <n>   Octave tolerance (default: 0)
  --enable-collapse                 Enable gravitational collapse (default)
  --disable-collapse                Disable gravitational collapse
  --max-segments <n>                Maximum segments to process
`,
  synthesize: `Usage: genesis.js synthesize [options]

Options:
  --model <file>            Model path (.pkl)
  --query <text>            Query text
  --debug                   Enable debug output
  --output <file>           Save synthesized proto (.pkl/.npy)
  --use-frequency           Use frequency-based matching
  --resonance-weighting     Enable resonance-weighted synthesis (default)
  --no-resonance-weighting  Disable resonance weighting
  --weight-function <type>  Weight function (linear|sqrt|log)
  --resonance-boost <n>     Resonance boost multiplier (default: 2.0)
  --distance-decay <n>      Distance weight factor (default: 0.5)
`,
};

function printHelp() {
  console.log(MAIN_HELP);
}

function printCommandHelp(command) {
  console.log(COMMAND_HELP[command] || MAIN_HELP);
}

function ensurePath(value, { mustExist, mustBeFile, mustBeDir, allowedExtensions }) {
  if (!value) {
    return;
  }

  const resolved = path.resolve(value);

  if (allowedExtensions && allowedExtensions.length > 0) {
    const ext = path.extname(resolved);
    if (!allowedExtensions.includes(ext)) {
      throw new Error(`Invalid file extension for ${value}. Allowed: ${allowedExtensions.join(", ")}`);
    }
  }

  if (mustExist) {
    if (!fs.existsSync(resolved)) {
      throw new Error(`Path does not exist: ${value}`);
    }

    const stat = fs.statSync(resolved);
    if (mustBeFile && !stat.isFile()) {
      throw new Error(`Expected file but found directory: ${value}`);
    }
    if (mustBeDir && !stat.isDirectory()) {
      throw new Error(`Expected directory but found file: ${value}`);
    }
  }
}

function parseNumber(value, label, kind = "float") {
  if (value === undefined || value === null || value === "") {
    return undefined;
  }

  const parsed = kind === "int" ? Number.parseInt(value, 10) : Number.parseFloat(value);
  if (Number.isNaN(parsed)) {
    throw new Error(`Invalid ${label}: ${value}`);
  }
  return parsed;
}

function handleUnimplemented(command, options) {
  console.error(`Command "${command}" is not yet implemented in the JavaScript port.`);
  console.error("Parsed options:", JSON.stringify(options, null, 2));
  return 1;
}

function parseCommand(command, argv) {
  const baseOptions = {
    help: { type: "boolean", short: "h" },
  };

  switch (command) {
    case "train": {
      const { values } = parseArgs({
        args: argv,
        options: {
          ...baseOptions,
          data: { type: "string", default: "/usr/lib/alembic/data/datasets/curated/foundation/" },
          output: { type: "string", default: "./models/genesis_foundation.pkl" },
          "use-gpu": { type: "boolean", default: false },
          "checkpoint-interval": { type: "string" },
          "max-documents": { type: "string" },
          "collapse-cosine-threshold": { type: "string", default: "0.85" },
          "collapse-harmonic-tolerance": { type: "string", default: "0.05" },
          "collapse-octave-tolerance": { type: "string", default: "1" },
          "enable-collapse": { type: "boolean", default: true },
          "disable-collapse": { type: "boolean", default: false },
        },
        allowPositionals: true,
      });

      if (values.help) {
        printCommandHelp("train");
        return 0;
      }

      if (values["disable-collapse"]) {
        values["enable-collapse"] = false;
      }

      ensurePath(values.data, { mustExist: true, mustBeDir: true });
      ensurePath(values.output, { allowedExtensions: [".pkl"] });

      const options = {
        data: values.data,
        output: values.output,
        useGpu: values["use-gpu"],
        checkpointInterval: parseNumber(values["checkpoint-interval"], "checkpoint interval", "int"),
        maxDocuments: parseNumber(values["max-documents"], "max documents", "int"),
        collapseCosineThreshold: parseNumber(values["collapse-cosine-threshold"], "collapse cosine threshold"),
        collapseHarmonicTolerance: parseNumber(values["collapse-harmonic-tolerance"], "collapse harmonic tolerance"),
        collapseOctaveTolerance: parseNumber(values["collapse-octave-tolerance"], "collapse octave tolerance", "int"),
        enableCollapse: values["enable-collapse"],
      };

      return handleUnimplemented(command, options);
    }
    case "chat": {
      const { values } = parseArgs({
        args: argv,
        options: {
          ...baseOptions,
          model: { type: "string", default: "./models/genesis_foundation.pkl" },
          stream: { type: "boolean", default: false },
          "show-stats": { type: "boolean", default: false },
          "save-on-exit": { type: "boolean", default: true },
        },
        allowPositionals: true,
      });

      if (values.help) {
        printCommandHelp("chat");
        return 0;
      }

      ensurePath(values.model, { mustExist: true, mustBeFile: true, allowedExtensions: [".pkl"] });

      const options = {
        model: values.model,
        stream: values.stream,
        showStats: values["show-stats"],
        saveOnExit: values["save-on-exit"],
      };

      return handleUnimplemented(command, options);
    }
    case "eval": {
      const { values } = parseArgs({
        args: argv,
        options: {
          ...baseOptions,
          model: { type: "string", default: "./models/genesis_foundation.pkl" },
          "test-cases": { type: "string", default: "./tests/test_cases.json" },
          output: { type: "string", default: "./results/eval_results.json" },
        },
        allowPositionals: true,
      });

      if (values.help) {
        printCommandHelp("eval");
        return 0;
      }

      ensurePath(values.model, { mustExist: true, mustBeFile: true, allowedExtensions: [".pkl"] });
      ensurePath(values["test-cases"], { mustExist: true, mustBeFile: true, allowedExtensions: [".json"] });
      ensurePath(values.output, { allowedExtensions: [".json"] });

      const options = {
        model: values.model,
        testCases: values["test-cases"],
        output: values.output,
      };

      return handleUnimplemented(command, options);
    }
    case "test": {
      const { values } = parseArgs({
        args: argv,
        options: baseOptions,
        allowPositionals: true,
      });

      if (values.help) {
        printCommandHelp("test");
        return 0;
      }

      return handleUnimplemented(command, {});
    }
    case "discover": {
      const { values } = parseArgs({
        args: argv,
        options: {
          ...baseOptions,
          input: { type: "string" },
          output: { type: "string", default: "/usr/lib/alembic/checkpoints/genesis/text_memory.pkl" },
          "dual-path": { type: "boolean", default: false },
          modality: { type: "string", default: "text" },
          "phase-coherence-threshold": { type: "string", default: "0.1" },
          "link-cross-modal": { type: "boolean", default: false },
          "collapse-harmonic-tolerance": { type: "string", default: "0.05" },
          "collapse-cosine-threshold": { type: "string", default: "0.85" },
          "collapse-octave-tolerance": { type: "string", default: "0" },
          "enable-collapse": { type: "boolean", default: true },
          "disable-collapse": { type: "boolean", default: false },
          "max-segments": { type: "string" },
        },
        allowPositionals: true,
      });

      if (values.help) {
        printCommandHelp("discover");
        return 0;
      }

      if (!values.input) {
        throw new Error("--input is required for discover");
      }

      if (values["disable-collapse"]) {
        values["enable-collapse"] = false;
      }

      ensurePath(values.input, { mustExist: true, mustBeFile: true });
      ensurePath(values.output, { allowedExtensions: [".pkl"] });

      const options = {
        input: values.input,
        output: values.output,
        dualPath: values["dual-path"],
        modality: values.modality,
        phaseCoherenceThreshold: parseNumber(values["phase-coherence-threshold"], "phase coherence threshold"),
        linkCrossModal: values["link-cross-modal"],
        collapseHarmonicTolerance: parseNumber(values["collapse-harmonic-tolerance"], "collapse harmonic tolerance"),
        collapseCosineThreshold: parseNumber(values["collapse-cosine-threshold"], "collapse cosine threshold"),
        collapseOctaveTolerance: parseNumber(values["collapse-octave-tolerance"], "collapse octave tolerance", "int"),
        enableCollapse: values["enable-collapse"],
        maxSegments: parseNumber(values["max-segments"], "max segments", "int"),
      };

      return handleUnimplemented(command, options);
    }
    case "synthesize": {
      const { values } = parseArgs({
        args: argv,
        options: {
          ...baseOptions,
          model: { type: "string" },
          query: { type: "string" },
          debug: { type: "boolean", default: false },
          output: { type: "string" },
          "use-frequency": { type: "boolean", default: false },
          "resonance-weighting": { type: "boolean", default: true },
          "no-resonance-weighting": { type: "boolean", default: false },
          "weight-function": { type: "string", default: "linear" },
          "resonance-boost": { type: "string", default: "2.0" },
          "distance-decay": { type: "string", default: "0.5" },
        },
        allowPositionals: true,
      });

      if (values.help) {
        printCommandHelp("synthesize");
        return 0;
      }

      if (!values.model) {
        throw new Error("--model is required for synthesize");
      }
      if (!values.query) {
        throw new Error("--query is required for synthesize");
      }

      if (values["no-resonance-weighting"]) {
        values["resonance-weighting"] = false;
      }

      ensurePath(values.model, { mustExist: true, mustBeFile: true, allowedExtensions: [".pkl"] });
      ensurePath(values.output, { allowedExtensions: [".pkl", ".npy"] });

      const options = {
        model: values.model,
        query: values.query,
        debug: values.debug,
        output: values.output,
        useFrequency: values["use-frequency"],
        resonanceWeighting: values["resonance-weighting"],
        weightFunction: values["weight-function"],
        resonanceBoost: parseNumber(values["resonance-boost"], "resonance boost"),
        distanceDecay: parseNumber(values["distance-decay"], "distance decay"),
      };

      return handleUnimplemented(command, options);
    }
    default:
      printHelp();
      return 1;
  }
}

function main() {
  const argv = process.argv.slice(2);
  if (argv.length === 0 || argv.includes("-h") || argv.includes("--help")) {
    printHelp();
    return 0;
  }

  const [command, ...rest] = argv;
  if (!COMMAND_HELP[command]) {
    console.error(`Unknown command: ${command}`);
    printHelp();
    return 1;
  }

  try {
    return parseCommand(command, rest);
  } catch (error) {
    console.error(error.message);
    return 1;
  }
}

process.exitCode = main();
