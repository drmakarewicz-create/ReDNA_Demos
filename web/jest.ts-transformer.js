const ts = require('typescript');

const compilerOptions = {
  module: ts.ModuleKind.CommonJS,
  jsx: ts.JsxEmit.ReactJSX,
  target: ts.ScriptTarget.ES2017,
  esModuleInterop: true,
  moduleResolution: ts.ModuleResolutionKind.Node10,
  resolveJsonModule: true,
  allowJs: true,
};

module.exports = {
  process(sourceText, sourcePath) {
    const result = ts.transpileModule(sourceText, {
      compilerOptions,
      fileName: sourcePath,
      reportDiagnostics: false,
    });

    return {
      code: result.outputText,
      map: result.sourceMapText || null,
    };
  },
};
