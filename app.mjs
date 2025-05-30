// @ts-check
import { defineConfig, createNotesQuery } from "./.app/app-config.js";

export default defineConfig({
  title: "Eleventy Notes",
  description:
    "A simple, lightweight, and flexible note-taking template for Eleventy.",
  editThisNote: {
    url: "https://github.com/rothsandro/eleventy-notes/edit/{{branch}}/{{file}}",
  },
  staticAssets: {
    paths: { "public/": "/" },
  },
  ignores: ["README.md"],
  customProperties: {
    properties: [
      {
        path: "props",
        options: {
          date: {
            locale: "en-US",
          },
        },
      },
    ],
  },
  sidebar: {
    links: [
      {
        url: "https://github.com/MingoDynasty/Mingo-Notes",
        label: "GitHub / Support",
        icon: "github",
      },
    ],
    sections: [
      {
        label: "Valorant",
        groups: [
          {
            query: createNotesQuery({
              // pattern: "^/[^/]+$",
              pattern: "^/Valorant/",
              // tags: ["valorant"],
              tree: {
                replace: {
                  "^/\\w+": "",
                },
              },
            }),
          },
        ],
      },
      {
        label: "Street Fighter 6",
        groups: [
          {
            query: createNotesQuery({
              // pattern: "^/[^/]+$",
              pattern: "^/SF6/",
              tags: ["sf6"],
            }),
          },
        ],
      },
    ],
  },
  tags: {
    map: {
      "dynamic-content": "dynamic content",
    },
  },
});
