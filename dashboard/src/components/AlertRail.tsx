"use client";

import { useState, useEffect, useMemo, useCallback } from "react";

// ─── Types ───────────────────────────────────────────────────────────────────

export interface Alert {
  module: string;
  event_type: string;
  zone_id: string;
  severity: string;
  camera_id: string;
  timestamp: number;
  object_id: string;
  evidence: string;
}

export interface AlertCard {
  key: string;
  alert: Alert;
  count: number;
  lastSeen: number;
  firstSeen: number;
}

interface InfoSummary {
  cameraId: string;
  count: number;
  lastSeen: number;
  firstSeen: number;
  /** Label derived from the most recent event_type for this camera */
  label: string;
  /** Rolling buffer of the most recent individual events (max 5) */
  recentEvents: Alert[];
}

interface AlertRailProps {
  /** Raw alert cards produced by the parent page's SSE ingestion. */
  alertCards: AlertCard[];
  /** If true, render a "CLEAR ALERTS" button in the header. */
  showClearButton?: boolean;
  /** Callback fired when the clear button is pressed. */
  onClear?: () => void;
  /** Optional extra element rendered inside the header row (e.g. Commander Login). */
  headerExtra?: React.ReactNode;
}

// ─── Constants ───────────────────────────────────────────────────────────────

const DECAY_MS = 30_000;
const CLEANUP_INTERVAL_MS = 5_000;
const MAX_RECENT = 5;

/** Friendly per-camera labels for the collapsed info row. */
const CAMERA_LABELS: Record<string, string> = {
  cam_01: "Persons detected",
  cam_02: "Vehicles detected",
  cam_03: "Plates read",
  cam_04: "Behavioral events",
  cam_05: "Fence events",
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

const DEDUP_KEY = (a: Alert) =>
  ["module_1", "module_2", "module_4"].includes(a.module)
    ? `${a.event_type}|${a.camera_id}|${a.zone_id}|${a.object_id}`
    : `${a.event_type}|${a.camera_id}|${a.zone_id}`;

function isActionable(severity: string): boolean {
  return severity === "critical" || severity === "warning";
}

function severityBorderClass(severity: string): string {
  switch (severity) {
    case "critical":
      return "bg-[var(--color-critical)]";
    case "warning":
      return "bg-[var(--color-warning)]";
    default:
      return "bg-green-400";
  }
}

function severityBadgeClass(severity: string): string {
  switch (severity) {
    case "critical":
      return "bg-[var(--color-critical)]";
    case "warning":
      return "bg-[var(--color-warning)]";
    default:
      return "bg-green-600";
  }
}

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString();
}

function formatTimestamp(ts: number): string {
  // Alert timestamps from Python are epoch seconds, JS timestamps are ms
  return new Date(ts * 1000).toLocaleTimeString();
}

// ─── Sub-components ──────────────────────────────────────────────────────────

/** Small clickable integrity badge — calls verify API on demand. */
function IntegrityBadge({ alert }: { alert: Alert }) {
  const [status, setStatus] = useState<
    "idle" | "loading" | "VERIFIED" | "TAMPERED" | "NOT_YET_ANCHORED" | "UNAVAILABLE" | "error"
  >("idle");
  const [detail, setDetail] = useState<string | null>(null);

  const eventId = [
    alert.module,
    alert.camera_id,
    alert.event_type,
    alert.object_id,
    String(alert.timestamp),
  ].join("|");

  const verify = async () => {
    setStatus("loading");
    try {
      const res = await fetch(
        `/api/ledger/verify/${encodeURIComponent(eventId)}`
      );
      const data = await res.json();
      setStatus(data.status || "error");
      setDetail(
        data.status === "VERIFIED"
          ? `Block #${data.anchored_block}`
          : data.detail || null
      );
    } catch {
      setStatus("error");
      setDetail("Could not reach verify service");
    }
  };

  const colorMap: Record<string, string> = {
    idle: "text-[var(--color-muted)] border-[var(--color-hair)]",
    loading: "text-[var(--color-active)] border-[var(--color-active)] animate-pulse",
    VERIFIED: "text-green-400 border-green-400",
    TAMPERED: "text-[var(--color-critical)] border-[var(--color-critical)]",
    NOT_YET_ANCHORED: "text-yellow-400 border-yellow-400",
    UNAVAILABLE: "text-[var(--color-muted)] border-[var(--color-hair)]",
    error: "text-[var(--color-muted)] border-[var(--color-hair)]",
  };

  const label =
    status === "idle"
      ? "⛓ Verify"
      : status === "loading"
        ? "⛓ …"
        : status === "VERIFIED"
          ? "⛓ ✓"
          : status === "TAMPERED"
            ? "⛓ ✗"
            : status === "NOT_YET_ANCHORED"
              ? "⛓ ⏳"
              : "⛓ —";

  return (
    <button
      onClick={verify}
      title={detail || "Click to verify on-chain integrity"}
      className={`font-mono text-[9px] px-1.5 py-0.5 border rounded cursor-pointer hover:opacity-80 transition-opacity ${colorMap[status]}`}
    >
      {label}
    </button>
  );
}

/** A full-size alert card for critical/warning events. */
function ActionableCard({ card }: { card: AlertCard }) {
  return (
    <div className="relative pl-3 p-3 bg-[var(--color-void)] border border-[var(--color-hair)] text-sm animate-[fadeIn_150ms_ease-out]">
      <div
        className={`absolute left-0 top-0 bottom-0 w-[3px] ${severityBorderClass(card.alert.severity)}`}
      />
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="font-mono text-xs text-[var(--color-muted)] mb-1">
            {formatTimestamp(card.alert.timestamp)} | {card.alert.camera_id}
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <span>
              {card.alert.event_type} — {card.alert.zone_id}
            </span>
            {card.count > 1 && (
              <span
                className={`${severityBadgeClass(card.alert.severity)} text-white text-[10px] font-mono px-1.5 py-0.5 rounded`}
              >
                ×{card.count}
              </span>
            )}
          </div>
          {card.alert.evidence && (
            <div className="text-xs text-[var(--color-muted)] mt-1">
              {card.alert.evidence}
            </div>
          )}
        </div>
        <div className="text-right text-[10px] text-[var(--color-muted)] shrink-0 flex flex-col items-end gap-1">
          <div>First: {formatTime(card.firstSeen)}</div>
          <div>Last: {formatTime(card.lastSeen)}</div>
          <IntegrityBadge alert={card.alert} />
        </div>
      </div>
    </div>
  );
}

/** A collapsed summary row for info-level events from one camera. */
function InfoSummaryRow({ summary }: { summary: InfoSummary }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-[var(--color-void)] border border-[var(--color-hair)] text-sm">
      {/* Collapsed header row */}
      <button
        onClick={() => setExpanded((prev) => !prev)}
        className="w-full flex items-center gap-2 px-3 py-2.5 text-left hover:bg-[var(--color-panel)] transition-colors"
      >
        {/* Green left accent (thin) */}
        <div className="w-[3px] self-stretch bg-green-400/40 shrink-0 -ml-3 mr-1" />

        {/* Chevron */}
        <svg
          className={`w-3 h-3 text-[var(--color-muted)] shrink-0 transition-transform duration-150 ${expanded ? "rotate-90" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>

        {/* Camera ID */}
        <span className="font-mono text-[11px] text-[var(--color-active)] shrink-0">
          {summary.cameraId.toUpperCase().replace("_", "-")}
        </span>

        {/* Label */}
        <span className="text-xs text-[var(--color-muted)] truncate flex-1">
          {summary.label}
        </span>

        {/* Count badge */}
        <span className="bg-green-600/80 text-white text-[10px] font-mono px-1.5 py-0.5 rounded shrink-0">
          {summary.count}
        </span>
      </button>

      {/* Expanded detail list */}
      {expanded && (
        <div className="border-t border-[var(--color-hair)] divide-y divide-[var(--color-hair)]">
          {summary.recentEvents.length === 0 ? (
            <div className="px-4 py-2 text-xs text-[var(--color-muted)] font-mono">
              No recent events
            </div>
          ) : (
            summary.recentEvents.map((evt, i) => (
              <div
                key={`${evt.camera_id}-${evt.timestamp}-${evt.object_id}-${i}`}
                className="px-4 py-2 text-xs"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-[var(--color-muted)]">
                    {formatTimestamp(evt.timestamp)}
                  </span>
                  <span className="text-[var(--color-primary)] truncate flex-1 text-right">
                    {evt.evidence || evt.event_type}
                  </span>
                </div>
                {evt.object_id && (
                  <div className="font-mono text-[10px] text-[var(--color-muted)] mt-0.5">
                    ID: {evt.object_id}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────────────────────────

export function AlertRail({
  alertCards,
  showClearButton,
  onClear,
  headerExtra,
}: AlertRailProps) {
  // ── Separate actionable (critical/warning) from info ─────────────────────
  const actionableCards = useMemo(
    () => alertCards.filter((c) => isActionable(c.alert.severity)),
    [alertCards],
  );

  const infoCards = useMemo(
    () => alertCards.filter((c) => !isActionable(c.alert.severity)),
    [alertCards],
  );

  // ── Aggregate info cards into per-camera summaries ───────────────────────
  const infoSummaries = useMemo(() => {
    const map = new Map<string, InfoSummary>();

    for (const card of infoCards) {
      const camId = card.alert.camera_id;
      const existing = map.get(camId);

      if (existing) {
        existing.count += card.count;
        existing.lastSeen = Math.max(existing.lastSeen, card.lastSeen);
        existing.firstSeen = Math.min(existing.firstSeen, card.firstSeen);
        // Add latest event to the front of the recent buffer
        existing.recentEvents.unshift(card.alert);
        if (existing.recentEvents.length > MAX_RECENT) {
          existing.recentEvents.length = MAX_RECENT;
        }
      } else {
        map.set(camId, {
          cameraId: camId,
          count: card.count,
          lastSeen: card.lastSeen,
          firstSeen: card.firstSeen,
          label:
            CAMERA_LABELS[camId] ||
            `${card.alert.event_type} events`,
          recentEvents: [card.alert],
        });
      }
    }

    // Sort by most recent activity
    return Array.from(map.values()).sort(
      (a, b) => b.lastSeen - a.lastSeen,
    );
  }, [infoCards]);

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="w-80 shrink-0 border-l border-[var(--color-hair)] bg-[var(--color-panel)] flex flex-col">
      {/* Header */}
      <div className="p-3 border-b border-[var(--color-hair)] uppercase tracking-wider text-xs font-semibold text-[var(--color-muted)] flex justify-between items-center">
        <span>Alert Rail</span>
        <div className="flex items-center gap-2">
          {showClearButton && onClear && (
            <button
              onClick={onClear}
              className="bg-[var(--color-void)] border border-[var(--color-critical)] text-[var(--color-critical)] font-mono text-[10px] px-2 py-1 hover:bg-[var(--color-critical)] hover:text-white transition-colors shadow-[0_0_8px_rgba(255,0,0,0.3)]"
            >
              CLEAR ALERTS
            </button>
          )}
          {headerExtra}
        </div>
      </div>

      {/* Scrollable body */}
      <div className="flex-1 overflow-y-auto">
        {/* ── Section 1: ALERTS (critical / warning) ────────────────────── */}
        <div className="p-2">
          <div className="font-mono text-[10px] uppercase tracking-wider text-[var(--color-muted)] mb-2 px-1 flex items-center gap-2">
            <span>Alerts</span>
            {actionableCards.length > 0 && (
              <span className="bg-[var(--color-critical)] text-white text-[9px] font-mono px-1.5 py-0.5 rounded-full">
                {actionableCards.length}
              </span>
            )}
          </div>

          {actionableCards.length === 0 ? (
            <div className="p-3 text-center text-[var(--color-muted)] text-xs font-mono">
              No active alerts
            </div>
          ) : (
            <div className="space-y-2">
              {actionableCards.map((card) => (
                <ActionableCard key={card.key} card={card} />
              ))}
            </div>
          )}
        </div>

        {/* ── Divider ───────────────────────────────────────────────────── */}
        <div className="mx-2 border-t border-[var(--color-hair)]" />

        {/* ── Section 2: ACTIVITY FEED (info, collapsed per camera) ───── */}
        <div className="p-2">
          <div className="font-mono text-[10px] uppercase tracking-wider text-[var(--color-muted)] mb-2 px-1">
            Activity Feed
          </div>

          {infoSummaries.length === 0 ? (
            <div className="p-3 text-center text-[var(--color-muted)] text-xs font-mono">
              No recent activity
            </div>
          ) : (
            <div className="space-y-1.5">
              {infoSummaries.map((summary) => (
                <InfoSummaryRow key={summary.cameraId} summary={summary} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Shared Hook: SSE Alert Ingestion ────────────────────────────────────────

/**
 * Custom hook that manages the SSE connection and alert card state.
 * Used by both the Operator and Commander pages.
 */
export function useAlertCards() {
  const [alertCards, setAlertCards] = useState<AlertCard[]>([]);

  // SSE connection
  useEffect(() => {
    let mounted = true;
    const eventSource = new EventSource("/api/alerts");

    const dedupKey = (a: Alert) =>
      ["module_1", "module_2", "module_4"].includes(a.module)
        ? `${a.event_type}|${a.camera_id}|${a.zone_id}|${a.object_id}`
        : `${a.event_type}|${a.camera_id}|${a.zone_id}`;

    eventSource.onmessage = (event) => {
      if (!mounted) return;
      try {
        const newAlert: Alert = JSON.parse(event.data);
        const key = dedupKey(newAlert);
        const now = Date.now();

        setAlertCards((prev) => {
          const existingIdx = prev.findIndex((c) => c.key === key);
          if (existingIdx >= 0) {
            const updated = [...prev];
            updated[existingIdx] = {
              ...updated[existingIdx],
              count: updated[existingIdx].count + 1,
              lastSeen: now,
              alert: newAlert,
            };
            const [card] = updated.splice(existingIdx, 1);
            return [card, ...updated];
          } else {
            const card: AlertCard = {
              key,
              alert: newAlert,
              count: 1,
              lastSeen: now,
              firstSeen: now,
            };
            return [card, ...prev].slice(0, 50);
          }
        });
      } catch (err) {
        console.error("Failed to parse alert:", err);
      }
    };

    eventSource.onerror = () => {
      if (mounted) {
        eventSource.close();
      }
    };

    return () => {
      mounted = false;
      eventSource.close();
    };
  }, []);

  // Decay cleanup
  useEffect(() => {
    const interval = setInterval(() => {
      const now = Date.now();
      setAlertCards((prev) => prev.filter((c) => now - c.lastSeen < DECAY_MS));
    }, CLEANUP_INTERVAL_MS);
    return () => clearInterval(interval);
  }, []);

  const clearAlerts = useCallback(() => setAlertCards([]), []);

  return { alertCards, clearAlerts };
}
