/*
 * The token contract: every theme must define every token listed here.
 * `mode: true` groups must also be redefined in the theme's dark block.
 * sync-tokens.py reads this file, so keep one token per quoted string.
 */
window.TOKEN_CONTRACT = [
  {
    group: "Colour", mode: true, tokens: [
      "--surface-0", "--surface-1", "--surface-2", "--surface-3",
      "--border", "--border-strong",
      "--text-1", "--text-2", "--text-3", "--text-on-primary",
      "--color-primary", "--color-primary-hover", "--color-secondary", "--color-accent",
      "--color-success", "--color-warning", "--color-danger", "--color-info",
      "--focus-ring", "--overlay",
      "--shadow-1", "--shadow-2", "--shadow-3"
    ]
  },
  {
    group: "Type", mode: false, tokens: [
      "--font-display", "--font-body", "--font-mono",
      "--weight-regular", "--weight-medium", "--weight-bold", "--weight-display",
      "--tracking-display", "--case-display", "--leading-tight", "--leading-body",
      "--text-xs", "--text-sm", "--text-base", "--text-lg",
      "--text-xl", "--text-2xl", "--text-3xl", "--text-4xl"
    ]
  },
  {
    group: "Space", mode: false, tokens: [
      "--space-1", "--space-2", "--space-3", "--space-4", "--space-5",
      "--space-6", "--space-7", "--space-8", "--space-9", "--space-10"
    ]
  },
  {
    group: "Shape", mode: false, tokens: [
      "--radius-sm", "--radius-md", "--radius-lg", "--radius-xl", "--radius-pill"
    ]
  },
  {
    group: "Motion", mode: false, tokens: [
      "--duration-fast", "--duration-base", "--duration-slow",
      "--ease-standard", "--ease-emphasized", "--ease-spring"
    ]
  }
];
