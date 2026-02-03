#!/usr/bin/env node
"use strict";

const { parseArgs } = require("node:util");
const fs = require("node:fs");
const path = require("node:path");

const DEFAULT_DB_PATH = "./data/genesis_db.json";

const MAIN_HELP = `Genesis - Text Learning System (JavaScript port)

Usage:
  genesis.js <command> [options]

Commands:
  train       Train on foundation data
  chat        Interactive conversation
  eval        Run A/B evaluation tests
  test        Test system components
  service     Run the realtime service backend
  ui          Run the visualization UI dev server
  sql         Run the SQL API backend
  mysql       Run the MySQL-compatible gateway
  demo        Run a bundled Python demo
  doctor      Validate local environment setup
  dev         Run visualization, SQL API, optional MySQL, and UI together
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
  service: `Usage: genesis.js service [options]

Options:
  --host <host>        Bind host (default: 0.0.0.0)
  --port <port>        Bind port (default: 8000)
  --reload             Enable auto-reload (development only)
  --log-level <level>  Uvicorn log level (default: info)
  --python <path>      Python executable (overrides GENESIS_PYTHON_BIN)

Environment:
  GENESIS_PYTHON_BIN   Python executable to use (falls back to python3, python)
`,
  ui: `Usage: genesis.js ui [options]

Options:
  --host <host>        Bind host (default: 0.0.0.0)
  --port <port>        Bind port (default: 5173)
`,
  sql: `Usage: genesis.js sql [options]

Options:
  --host <host>        Bind host (default: 0.0.0.0)
  --port <port>        Bind port (default: 8001)
  --reload             Enable auto-reload (development only)
  --log-level <level>  Uvicorn log level (default: info)
  --python <path>      Python executable (overrides GENESIS_PYTHON_BIN)
  --db-path <file>     Genesis DB JSON path (default: ./data/genesis_db.json)

Environment:
  GENESIS_DB_PATH      Genesis DB JSON path override
  GENESIS_PYTHON_BIN   Python executable to use (falls back to python3, python)
`,
  mysql: `Usage: genesis.js mysql [options]

Options:
  --host <host>        Bind host (default: 0.0.0.0)
  --port <port>        Bind port (default: 3306)
  --python <path>      Python executable (overrides GENESIS_PYTHON_BIN)
  --db-path <file>     Genesis DB JSON path (default: ./data/genesis_db.json)

Environment:
  GENESIS_DB_PATH      Genesis DB JSON path override
  GENESIS_MYSQL_HOST   MySQL host override
  GENESIS_MYSQL_PORT   MySQL port override
  GENESIS_PYTHON_BIN   Python executable to use (falls back to python3, python)
`,
  demo: `Usage: genesis.js demo <name> [options]

Available demos:
  fft-roundtrip
  memory-integration
  hierarchical-synthesis

Options:
  --python <path>      Python executable (overrides GENESIS_PYTHON_BIN)

Environment:
  GENESIS_PYTHON_BIN   Python executable to use (falls back to python3, python)
`,
  doctor: `Usage: genesis.js doctor

Checks:
  - Node.js, npm, and Python availability
  - Python uvicorn module
  - UI workspace presence
`,
  dev: `Usage: genesis.js dev [options]

Options:
  --host <host>            Visualization backend host (default: 0.0.0.0)
  --port <port>            Visualization backend port (default: 8000)
  --sql-host <host>        SQL API host (default: 0.0.0.0)
  --sql-port <port>        SQL API port (default: 8001)
  --ui-host <host>         UI dev server host (default: 0.0.0.0)
  --ui-port <port>         UI dev server port (default: 5173)
  --mysql                  Start the MySQL-compatible gateway
  --mysql-host <host>      MySQL host (default: 0.0.0.0)
  --mysql-port <port>      MySQL port (default: 3306)
  --db-path <file>         Genesis DB JSON path (default: ./data/genesis_db.json)
  --reload                 Enable auto-reload for Python services
  --log-level <level>      Uvicorn log level (default: info)
  --python <path>          Python executable (overrides GENESIS_PYTHON_BIN)

Environment:
  GENESIS_DB_PATH          Genesis DB JSON path override
  GENESIS_MYSQL_HOST       MySQL host override
  GENESIS_MYSQL_PORT       MySQL port override
  GENESIS_PYTHON_BIN       Python executable to use (falls back to python3, python)
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

function resolvePythonExecutable(options) {
  const { spawnSync } = require("node:child_process");
  const candidates = [
    options.python,
    process.env.GENESIS_PYTHON_BIN,
    "python3",
    "python",
  ].filter(Boolean);

  for (const candidate of candidates) {
    const result = spawnSync(candidate, ["-V"], { stdio: "ignore" });
    if (!result.error && result.status === 0) {
      return candidate;
    }
    if (candidate === options.python || candidate === process.env.GENESIS_PYTHON_BIN) {
      throw new Error(
        `Unable to run Python executable "${candidate}". ` +
          "Check that the path is correct and that it is on PATH."
      );
    }
  }

  throw new Error(
    "No Python executable found. Install Python or set GENESIS_PYTHON_BIN/--python to a valid executable on your PATH."
  );
}

function resolveNpmExecutable() {
  const { spawnSync } = require("node:child_process");
  const candidates = ["npm"];
  for (const candidate of candidates) {
    const result = spawnSync(candidate, ["-v"], { stdio: "ignore" });
    if (!result.error && result.status === 0) {
      return candidate;
    }
  }
  throw new Error("npm is required to run the UI dev server. Install Node.js/npm and try again.");
}

function handleUnimplemented(command, options) {
  console.error(`Command "${command}" is not yet implemented in the JavaScript port.`);
  console.error("Parsed options:", JSON.stringify(options, null, 2));
  return 1;
}

function createProcessManager() {
  const children = new Map();
  let shuttingDown = false;

  const shutdown = (reason) => {
    if (shuttingDown) {
      return;
    }
    shuttingDown = true;
    for (const { child, name } of children.values()) {
      if (!child.killed) {
        child.kill("SIGTERM");
        setTimeout(() => {
          if (!child.killed) {
            child.kill("SIGKILL");
          }
        }, 1500);
      }
      if (reason && name) {
        console.error(`Stopping ${name}...`);
      }
    }
  };

  const track = (name, child) => {
    children.set(child.pid, { name, child });
    child.on("exit", (code, signal) => {
      children.delete(child.pid);
      if (!shuttingDown) {
        const label = signal ? `${signal}` : `exit code ${code ?? 0}`;
        console.error(`${name} exited with ${label}. Shutting down remaining processes...`);
        process.exitCode = code === null || code === undefined ? 1 : code;
        shutdown("child-exit");
      }
    });
    return child;
  };

  process.on("SIGINT", () => shutdown("SIGINT"));
  process.on("SIGTERM", () => shutdown("SIGTERM"));
  process.on("exit", () => shutdown("exit"));

  return { track, shutdown };
}

function runService(options) {
  const { spawn } = require("node:child_process");
  const manager = createProcessManager();
  const python = resolvePythonExecutable(options);
  const args = [
    "-m",
    "uvicorn",
    "src.visualization.server:app",
    "--host",
    options.host,
    "--port",
    String(options.port),
    "--log-level",
    options.logLevel,
  ];

  if (options.reload) {
    args.push("--reload");
  }

  const child = spawn(python, args, { stdio: "inherit" });
  manager.track("visualization service", child);
  return 0;
}

function runSql(options) {
  const { spawn } = require("node:child_process");
  const manager = createProcessManager();
  const python = resolvePythonExecutable(options);
  const args = [
    "-m",
    "uvicorn",
    "src.api.log_api:app",
    "--host",
    options.host,
    "--port",
    String(options.port),
    "--log-level",
    options.logLevel,
  ];

  if (options.reload) {
    args.push("--reload");
  }

  const env = { ...process.env, GENESIS_DB_PATH: options.dbPath };
  const child = spawn(python, args, { stdio: "inherit", env });
  manager.track("SQL API", child);
  return 0;
}

function runMysql(options) {
  const { spawn } = require("node:child_process");
  const manager = createProcessManager();
  const python = resolvePythonExecutable(options);
  const env = {
    ...process.env,
    GENESIS_DB_PATH: options.dbPath,
    GENESIS_MYSQL_HOST: options.host,
    GENESIS_MYSQL_PORT: String(options.port),
  };
  const child = spawn(python, ["-m", "src.api.mysql_server"], { stdio: "inherit", env });
  manager.track("MySQL gateway", child);
  return 0;
}

function runUi(options) {
  const { spawn } = require("node:child_process");
  const manager = createProcessManager();
  const npm = resolveNpmExecutable();
  const args = ["--prefix", "ui", "run", "dev", "--", "--host", options.host, "--port", String(options.port)];
  const child = spawn(npm, args, { stdio: "inherit" });
  manager.track("UI dev server", child);
  return 0;
}

function runDemo(options) {
  const { spawn } = require("node:child_process");
  const python = resolvePythonExecutable(options);
  const demoMap = new Map([
    ["fft-roundtrip", "demo_fft_roundtrip.py"],
    ["memory-integration", "demo_memory_integration.py"],
    ["hierarchical-synthesis", "demo_hierarchical_synthesis.py"],
  ]);
  const demoFile = demoMap.get(options.name) || options.name;
  const resolved = path.resolve("examples", demoFile);

  if (!fs.existsSync(resolved)) {
    throw new Error(`Unknown demo "${options.name}". Available demos: ${[...demoMap.keys()].join(", ")}`);
  }

  const manager = createProcessManager();
  const child = spawn(python, [resolved], { stdio: "inherit" });
  manager.track(`demo ${options.name}`, child);
  return 0;
}

function runDoctor() {
  const { spawnSync } = require("node:child_process");
  const checks = [];
  const recordCheck = (label, result, hint) => {
    checks.push({ label, result, hint });
  };

  const nodeResult = spawnSync("node", ["-v"], { encoding: "utf8" });
  recordCheck("Node.js", nodeResult.status === 0, nodeResult.stderr?.trim() || nodeResult.error?.message);

  const npmResult = spawnSync("npm", ["-v"], { encoding: "utf8" });
  recordCheck("npm", npmResult.status === 0, npmResult.stderr?.trim() || npmResult.error?.message);

  const pythonCandidates = [process.env.GENESIS_PYTHON_BIN, "python3", "python"].filter(Boolean);
  let pythonOk = false;
  let pythonName = "";
  for (const candidate of pythonCandidates) {
    const result = spawnSync(candidate, ["-V"], { encoding: "utf8" });
    if (result.status === 0) {
      pythonOk = true;
      pythonName = candidate;
      break;
    }
  }
  recordCheck("Python", pythonOk, pythonOk ? pythonName : "Install Python or set GENESIS_PYTHON_BIN.");

  if (pythonOk) {
    const uvicornResult = spawnSync(pythonName, ["-m", "uvicorn", "--version"], { encoding: "utf8" });
    recordCheck(
      "Python uvicorn module",
      uvicornResult.status === 0,
      uvicornResult.stderr?.trim() || uvicornResult.error?.message
    );
  } else {
    recordCheck("Python uvicorn module", false, "Python not available.");
  }

  const uiDirExists = fs.existsSync(path.resolve("ui"));
  recordCheck("UI workspace", uiDirExists, uiDirExists ? "" : "Missing ./ui directory.");

  let hasFailure = false;
  for (const check of checks) {
    const status = check.result ? "✓" : "✗";
    console.log(`${status} ${check.label}${check.hint ? ` (${check.hint})` : ""}`);
    if (!check.result) {
      hasFailure = true;
    }
  }

  return hasFailure ? 1 : 0;
}

function runDev(options) {
  const { spawn } = require("node:child_process");
  const manager = createProcessManager();
  const python = resolvePythonExecutable(options);
  const npm = resolveNpmExecutable();

  const sqlEnv = { ...process.env, GENESIS_DB_PATH: options.dbPath };
  const mysqlEnv = {
    ...process.env,
    GENESIS_DB_PATH: options.dbPath,
    GENESIS_MYSQL_HOST: options.mysqlHost,
    GENESIS_MYSQL_PORT: String(options.mysqlPort),
  };

  const serviceArgs = [
    "-m",
    "uvicorn",
    "src.visualization.server:app",
    "--host",
    options.host,
    "--port",
    String(options.port),
    "--log-level",
    options.logLevel,
  ];
  if (options.reload) {
    serviceArgs.push("--reload");
  }
  const serviceChild = spawn(python, serviceArgs, { stdio: "inherit" });
  manager.track("visualization service", serviceChild);

  const sqlArgs = [
    "-m",
    "uvicorn",
    "src.api.log_api:app",
    "--host",
    options.sqlHost,
    "--port",
    String(options.sqlPort),
    "--log-level",
    options.logLevel,
  ];
  if (options.reload) {
    sqlArgs.push("--reload");
  }
  const sqlChild = spawn(python, sqlArgs, { stdio: "inherit", env: sqlEnv });
  manager.track("SQL API", sqlChild);

  if (options.mysql) {
    const mysqlChild = spawn(python, ["-m", "src.api.mysql_server"], { stdio: "inherit", env: mysqlEnv });
    manager.track("MySQL gateway", mysqlChild);
  }

  const uiArgs = ["--prefix", "ui", "run", "dev", "--", "--host", options.uiHost, "--port", String(options.uiPort)];
  const uiChild = spawn(npm, uiArgs, { stdio: "inherit" });
  manager.track("UI dev server", uiChild);

  console.log("Genesis dev stack started:");
  console.log(`- Visualization backend: http://${options.host}:${options.port}`);
  console.log(`- SQL API: http://${options.sqlHost}:${options.sqlPort}`);
  if (options.mysql) {
    console.log(`- MySQL gateway: ${options.mysqlHost}:${options.mysqlPort}`);
  }
  console.log(`- UI: http://${options.uiHost}:${options.uiPort}`);

  return 0;
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
    case "service": {
      const { values } = parseArgs({
        args: argv,
        options: {
          ...baseOptions,
          host: { type: "string", default: "0.0.0.0" },
          port: { type: "string", default: "8000" },
          reload: { type: "boolean", default: false },
          "log-level": { type: "string", default: "info" },
          python: { type: "string" },
        },
        allowPositionals: true,
      });

      if (values.help) {
        printCommandHelp("service");
        return 0;
      }

      const options = {
        host: values.host,
        port: parseNumber(values.port, "port", "int"),
        reload: values.reload,
        logLevel: values["log-level"],
        python: values.python,
      };

      return runService(options);
    }
    case "ui": {
      const { values } = parseArgs({
        args: argv,
        options: {
          ...baseOptions,
          host: { type: "string", default: "0.0.0.0" },
          port: { type: "string", default: "5173" },
        },
        allowPositionals: true,
      });

      if (values.help) {
        printCommandHelp("ui");
        return 0;
      }

      const options = {
        host: values.host,
        port: parseNumber(values.port, "port", "int"),
      };

      return runUi(options);
    }
    case "sql": {
      const { values } = parseArgs({
        args: argv,
        options: {
          ...baseOptions,
          host: { type: "string", default: "0.0.0.0" },
          port: { type: "string", default: "8001" },
          reload: { type: "boolean", default: false },
          "log-level": { type: "string", default: "info" },
          "db-path": { type: "string", default: process.env.GENESIS_DB_PATH || DEFAULT_DB_PATH },
          python: { type: "string" },
        },
        allowPositionals: true,
      });

      if (values.help) {
        printCommandHelp("sql");
        return 0;
      }

      ensurePath(values["db-path"], { allowedExtensions: [".json"] });

      const options = {
        host: values.host,
        port: parseNumber(values.port, "port", "int"),
        reload: values.reload,
        logLevel: values["log-level"],
        python: values.python,
        dbPath: values["db-path"],
      };

      return runSql(options);
    }
    case "mysql": {
      const { values } = parseArgs({
        args: argv,
        options: {
          ...baseOptions,
          host: { type: "string", default: "0.0.0.0" },
          port: { type: "string", default: "3306" },
          "db-path": { type: "string", default: process.env.GENESIS_DB_PATH || DEFAULT_DB_PATH },
          python: { type: "string" },
        },
        allowPositionals: true,
      });

      if (values.help) {
        printCommandHelp("mysql");
        return 0;
      }

      ensurePath(values["db-path"], { allowedExtensions: [".json"] });

      const options = {
        host: values.host,
        port: parseNumber(values.port, "port", "int"),
        python: values.python,
        dbPath: values["db-path"],
      };

      return runMysql(options);
    }
    case "demo": {
      const { values, positionals } = parseArgs({
        args: argv,
        options: {
          ...baseOptions,
          python: { type: "string" },
        },
        allowPositionals: true,
      });

      if (values.help) {
        printCommandHelp("demo");
        return 0;
      }

      const name = positionals[0];
      if (!name) {
        throw new Error("Demo name is required. Example: genesis.js demo fft-roundtrip");
      }

      return runDemo({ name, python: values.python });
    }
    case "doctor": {
      const { values } = parseArgs({
        args: argv,
        options: baseOptions,
        allowPositionals: true,
      });

      if (values.help) {
        printCommandHelp("doctor");
        return 0;
      }

      return runDoctor();
    }
    case "dev": {
      const { values } = parseArgs({
        args: argv,
        options: {
          ...baseOptions,
          host: { type: "string", default: "0.0.0.0" },
          port: { type: "string", default: "8000" },
          "sql-host": { type: "string", default: "0.0.0.0" },
          "sql-port": { type: "string", default: "8001" },
          "ui-host": { type: "string", default: "0.0.0.0" },
          "ui-port": { type: "string", default: "5173" },
          mysql: { type: "boolean", default: false },
          "mysql-host": { type: "string", default: "0.0.0.0" },
          "mysql-port": { type: "string", default: "3306" },
          "db-path": { type: "string", default: process.env.GENESIS_DB_PATH || DEFAULT_DB_PATH },
          reload: { type: "boolean", default: false },
          "log-level": { type: "string", default: "info" },
          python: { type: "string" },
        },
        allowPositionals: true,
      });

      if (values.help) {
        printCommandHelp("dev");
        return 0;
      }

      ensurePath(values["db-path"], { allowedExtensions: [".json"] });

      const options = {
        host: values.host,
        port: parseNumber(values.port, "port", "int"),
        sqlHost: values["sql-host"],
        sqlPort: parseNumber(values["sql-port"], "sql port", "int"),
        uiHost: values["ui-host"],
        uiPort: parseNumber(values["ui-port"], "ui port", "int"),
        mysql: values.mysql,
        mysqlHost: values["mysql-host"],
        mysqlPort: parseNumber(values["mysql-port"], "mysql port", "int"),
        dbPath: values["db-path"],
        reload: values.reload,
        logLevel: values["log-level"],
        python: values.python,
      };

      return runDev(options);
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
