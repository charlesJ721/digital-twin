import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

// Local dev: symlinked Obsidian vault (src/content/notes → ~/Ars Longa Vita Brevis)
// CI build:  PUBLIC_NOTES_PATH=./public-notes (selected notes committed to repo)
const contentBase = process.env.PUBLIC_NOTES_PATH || './src/content/notes';

const notes = defineCollection({
  loader: glob({ pattern: '**/*.md', base: contentBase }),
  schema: z.object({
    title: z.string().optional(),
    创建: z.string().optional(),
    'dg-publish': z.boolean().optional().default(true),
    layer: z.enum(['范式层', '架构层', '手段层']).optional(),
    tags: z.array(z.string()).optional().default([]),
    stage: z.string().optional(),
    category: z.string().optional(),
  }),
});

export const collections = { notes };
