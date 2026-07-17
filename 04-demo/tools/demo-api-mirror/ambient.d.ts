declare module "@netlify/functions" {
  export interface Config {
    path?: string;
  }

  export interface Context {
    params: Record<string, string | undefined>;
  }
}

declare module "read-excel-file/node" {
  const readXlsxFile: any;
  export default readXlsxFile;
}

declare const Buffer: any;
