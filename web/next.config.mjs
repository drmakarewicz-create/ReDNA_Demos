const FALSEY = new Set(["", "0", "false", "off", "no"]);
const STRICT_RULES = [
  {
    name: "NEXT_PUBLIC_CORE_BYPASS_ALLOWED",
    allowed: new Set(["false"]),
    required: true,
    message: "NEXT_PUBLIC_CORE_BYPASS_ALLOWED must be set to 'false' for production builds."
  },
  {
    name: "DEV_LOOP_SKIP_RECOMPUTE",
    allowed: FALSEY,
    message: "Remove DEV_LOOP_SKIP_RECOMPUTE for production builds."
  },
  {
    name: "STACK_UP_SKIP_BOOTSTRAP",
    allowed: FALSEY,
    message: "STACK_UP_SKIP_BOOTSTRAP cannot be enabled in production."
  },
  {
    name: "READINESS_SKIP_CORE_HEALTH",
    allowed: FALSEY,
    message: "READINESS_SKIP_CORE_HEALTH cannot be enabled in production."
  }
];

const PREFIXES = ["NEXT_PUBLIC_", "DEV_", "STACK_", "READINESS_", "CORE_", "UCNRR_", "LLM_", "HC_", "AI_"];
const PATTERNS = ["MOCK", "SKIP", "BYPASS"];

const normalize = (value = "") => value.trim().toLowerCase();

const enforceProdFlags = () => {
  const violations = [];
  const monitored = new Set(STRICT_RULES.map((rule) => rule.name));

  for (const rule of STRICT_RULES) {
    const rawValue = process.env[rule.name] ?? "";
    const normalized = normalize(rawValue);
    const allowed = rule.allowed ?? FALSEY;
    if (rule.required && !rawValue) {
      violations.push(rule.message);
      continue;
    }
    if (rawValue && !allowed.has(normalized)) {
      violations.push(rule.message);
    }
  }

  for (const [key, value] of Object.entries(process.env)) {
    const upperKey = key.toUpperCase();
    if (monitored.has(key)) {
      continue;
    }
    if (!PREFIXES.some((prefix) => upperKey.startsWith(prefix))) {
      continue;
    }
    if (!PATTERNS.some((pattern) => upperKey.includes(pattern))) {
      continue;
    }
    if (!FALSEY.has(normalize(value))) {
      violations.push(`${key}=${value} violates mock/skip/bypass policy.`);
    }
  }

  if (violations.length) {
    throw new Error(
      `[Prod Safeguard] Unsafe environment flags detected:\n - ${violations.join("\n - ")}`
    );
  }
};

if (process.env.NODE_ENV === "production") {
  enforceProdFlags();
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  experimental: {
    typedRoutes: true
  }
};

export default nextConfig;
