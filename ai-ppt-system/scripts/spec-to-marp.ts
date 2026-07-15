import { escapeMarp, readSpec, writeText } from "./shared.ts";

const spec = readSpec();

const parts = [
  "---",
  "marp: true",
  "theme: business",
  "paginate: true",
  "size: 16:9",
  "---",
  ""
];

for (const slide of spec.slides) {
  if (slide.type === "cover") {
    parts.push("<!-- _class: cover -->");
    parts.push(`# ${escapeMarp(slide.title)}`);
    parts.push("");
    parts.push(`## ${escapeMarp(slide.message)}`);
  } else {
    parts.push(`<!-- _class: ${slide.type} -->`);
    parts.push(`# ${escapeMarp(slide.title)}`);
    parts.push("");
    parts.push(`**${escapeMarp(slide.message)}**`);
  }
  parts.push("");
  for (const point of slide.points) {
    parts.push(`- ${escapeMarp(point)}`);
  }
  parts.push("");
  parts.push(`<!-- speaker_note: ${escapeMarp(slide.speaker_note)} -->`);
  parts.push("");
  parts.push("---");
  parts.push("");
}

writeText(["output", "marp", "slides.md"], `${parts.join("\n").replace(/\n---\n$/, "\n")}`);
console.log("Generated output/marp/slides.md.");

