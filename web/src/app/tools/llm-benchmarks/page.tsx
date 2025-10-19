import NextDynamic from "next/dynamic";

const BenchmarksClient = NextDynamic(() => import("./page.client"), { ssr: false });

// App Router special export – keep this name to force dynamic rendering
export const dynamic = "force-dynamic";

export const metadata = {
  title: "LLM Benchmarks - ReDNA DevX",
};

export default function BenchmarksPage() {
  return <BenchmarksClient />;
}
