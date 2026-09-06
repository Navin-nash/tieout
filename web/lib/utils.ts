import { createCn } from "cn/config";

/**
 * `cn` (clsx + tailwind-merge), taught DESIGN.md's custom scales.
 *
 * Without this, the merge silently deletes design tokens. `cn("text-caption
 * text-sampled")` returned just `"text-sampled"`: tailwind-merge only knows the
 * stock scale, so an unrecognised `text-*` is assumed to be a text colour, and
 * two "colours" in one string means the later wins. Every badge lost its 12px
 * size that way - invisibly, because the class was still in the source.
 *
 * The three groups below are exactly the DESIGN.md namespaces that collide with
 * a stock group:
 *   font-size  - section 3.2's `text-display-*`, `text-heading-*`, `text-body*`,
 *                `text-caption`, `text-numeral-*` all look like `text-<colour>`.
 *   text-color - the disposition and ink colours, so the merge can still
 *                de-duplicate two colours correctly.
 *   tracking   - section 3.2's named tracking steps.
 *
 * Downstream surfaces get the fix for free by importing `cn` from here.
 */
export const cn = createCn({
  extend: {
    classGroups: {
      "font-size": [
        {
          text: [
            "display-2xl",
            "display-xl",
            "display-lg",
            "heading-md",
            "heading-sm",
            "body-lg",
            "body",
            "body-sm",
            "caption",
            "numeral-lg",
            "numeral-md",
            "numeral-sm",
          ],
        },
      ],
      "text-color": [
        {
          text: [
            "paper",
            "paper-inset",
            "ink",
            "ink-muted",
            "focus",
            "sampled",
            "escalate",
            "refuse",
          ],
        },
      ],
      tracking: [
        { tracking: ["display-2xl", "display-xl", "display-lg", "caption"] },
      ],
    },
  },
});
