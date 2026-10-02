"use client";

import { useState } from "react";

import { colors, fieldStyle, labelStyle, submitStyle } from "@/lib/formStyles";

import { createPlacement } from "./actions";

type Marker = {
  id: string;
  x: number;
  y: number;
  color: string;
  warning: boolean;
  valueLabel: string | null;
  title: string;
};

type Option = { id: string; label: string };

type Labels = {
  clickHint: string;
  noCoordinatesSelected: string;
  coordinatesSelected: string;
  targetTypeLabel: string;
  targetTypeSpace: string;
  targetTypeFunctionalLocation: string;
  targetIdLabel: string;
  addMarker: string;
};

/**
 * Seul composant client de cette page : capter la position d'un clic sur
 * l'image du plan pour la transformer en coordonnées normalisées (0 à 1,
 * indépendantes de la résolution — ADR 011, étape S4). La création elle-même
 * reste une action serveur ordinaire, comme le reste de la console.
 */
export function PlacementEditor({
  floorPlanId,
  imageUrl,
  markers,
  spaceOptions,
  locationOptions,
  labels,
}: {
  floorPlanId: string;
  imageUrl: string;
  markers: Marker[];
  spaceOptions: Option[];
  locationOptions: Option[];
  labels: Labels;
}) {
  const [ratio, setRatio] = useState<{ x: number; y: number } | null>(null);
  const [targetType, setTargetType] = useState<"space" | "functional_location">("space");

  function handleClick(event: React.MouseEvent<HTMLImageElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
    const y = Math.min(1, Math.max(0, (event.clientY - rect.top) / rect.height));
    setRatio({ x, y });
  }

  const options = targetType === "space" ? spaceOptions : locationOptions;

  return (
    <div>
      <p style={{ color: colors.textMuted }}>{labels.clickHint}</p>
      <div style={{ position: "relative", display: "inline-block", maxWidth: "100%" }}>
        {/* eslint-disable-next-line @next/next/no-img-element -- image distante, présignée, jamais optimisable par next/image */}
        <img
          src={imageUrl}
          alt=""
          onClick={handleClick}
          style={{ display: "block", maxWidth: "100%", cursor: "crosshair" }}
        />
        {markers.map((marker) => (
          <span
            key={marker.id}
            title={marker.title}
            style={{
              position: "absolute",
              left: `${marker.x * 100}%`,
              top: `${marker.y * 100}%`,
              transform: "translate(-50%, -50%)",
            }}
          >
            <span
              style={{
                display: "block",
                width: 12,
                height: 12,
                borderRadius: "50%",
                background: marker.color,
                border: "2px solid white",
                boxShadow: marker.warning
                  ? "0 0 0 1px rgba(0,0,0,0.3), 0 0 0 4px #dc2626"
                  : "0 0 0 1px rgba(0,0,0,0.3)",
              }}
            />
            {marker.valueLabel && (
              <span
                style={{
                  position: "absolute",
                  left: "50%",
                  top: "100%",
                  transform: "translate(-50%, 2px)",
                  whiteSpace: "nowrap",
                  fontSize: 11,
                  lineHeight: 1,
                  padding: "2px 4px",
                  borderRadius: 3,
                  background: "rgba(17, 24, 39, 0.85)",
                  color: "white",
                }}
              >
                {marker.valueLabel}
              </span>
            )}
          </span>
        ))}
        {ratio && (
          <span
            style={{
              position: "absolute",
              left: `${ratio.x * 100}%`,
              top: `${ratio.y * 100}%`,
              width: 16,
              height: 16,
              borderRadius: "50%",
              border: `2px dashed ${colors.accent}`,
              transform: "translate(-50%, -50%)",
            }}
          />
        )}
      </div>

      <p>{ratio ? labels.coordinatesSelected : labels.noCoordinatesSelected}</p>

      {ratio && (
        <form action={createPlacement} style={{ maxWidth: 400 }}>
          <input type="hidden" name="floor_plan_id" value={floorPlanId} />
          <input type="hidden" name="x_ratio" value={ratio.x} />
          <input type="hidden" name="y_ratio" value={ratio.y} />
          <label style={labelStyle}>
            {labels.targetTypeLabel}
            <select
              name="target_type"
              value={targetType}
              onChange={(event) =>
                setTargetType(event.target.value as "space" | "functional_location")
              }
              style={fieldStyle}
            >
              <option value="space">{labels.targetTypeSpace}</option>
              <option value="functional_location">{labels.targetTypeFunctionalLocation}</option>
            </select>
          </label>
          <label style={labelStyle}>
            {labels.targetIdLabel}
            <select name="target_id" required style={fieldStyle}>
              {options.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <button type="submit" style={submitStyle}>
            {labels.addMarker}
          </button>
        </form>
      )}
    </div>
  );
}
