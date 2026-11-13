import { ImageResponse } from "next/og";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          background: "#f7f8f8",
          color: "#1c2430",
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: 64,
          fontSize: 48,
        }}
      >
        <div>Blue Tender</div>
        <div style={{ fontSize: 28 }}>Funding and partners for marine energy</div>
      </div>
    ),
    size,
  );
}
