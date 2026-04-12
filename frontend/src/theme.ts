import { createTheme, MantineColorsTuple } from "@mantine/core";

const brand: MantineColorsTuple = [
  "#f0f4ff",
  "#dce6ff",
  "#b5c8ff",
  "#8aa8ff",
  "#678eff",
  "#4f7bff",
  "#4071ff",
  "#2e5ee6",
  "#1f52cf",
  "#0a44b8",
];

export const theme = createTheme({
  primaryColor: "brand",
  colors: { brand },
  defaultRadius: "md",
  fontFamily: "system-ui, -apple-system, sans-serif",
  components: {
    Paper: {
      defaultProps: { withBorder: true },
    },
  },
});
