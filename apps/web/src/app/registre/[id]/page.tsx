import Link from "next/link";

import { apiFetch, requireAccessToken } from "@/lib/api";
import { getLocale, getTranslator } from "@/lib/i18n";
import { type EquipmentStatus, type Passport, type PassportUnit, statusMessage } from "@/lib/passport";
import { type Locale, formatDate, formatDateTime, formatNumber } from "@/i18n/translator";

const sectionStyle = { borderTop: "1px solid #eee", paddingTop: 12, marginTop: 16 };
const sectionTitleStyle = { fontSize: 16, fontWeight: 600 as const, marginBottom: 8 };
const mutedStyle = { color: "#666" };
const strongStyle = { fontWeight: 600 as const };

export default async function EquipmentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const accessToken = await requireAccessToken();
  const translator = await getTranslator();
  const locale = await getLocale();
  const { t } = translator;

  const response = await apiFetch(`/graph/nodes/${id}/passport`, accessToken);
  if (!response.ok) {
    return (
      <main style={{ maxWidth: 720, margin: "40px auto", padding: "0 16px" }}>
        <Link href="/registre">← {t("common.back")}</Link>
        <p>{t("web.registre.equipment_not_found")}</p>
      </main>
    );
  }
  // Contrairement à /tags/{code} (utilisé par le mobile), cette route
  // renvoie directement l'objet passeport, sans enveloppe.
  const passport: Passport = await response.json();
  const unit = passport.physical_unit ?? passport.current_unit ?? null;
  const timeZone = passport.site?.timezone ?? null;
  const alarms = passport.open_alarms ?? [];

  return (
    <main style={{ maxWidth: 720, margin: "40px auto", padding: "0 16px" }}>
      <Link href="/registre">← {t("common.back")}</Link>

      {passport.functional_location && (
        <h1>
          {passport.functional_location.code} — {passport.functional_location.name}
        </h1>
      )}

      {passport.status && (
        <section style={sectionStyle}>
          <h2 style={sectionTitleStyle}>{t("mobile.passport.status")}</h2>
          <StatusLine status={passport.status} timeZone={timeZone} locale={locale} t={t} />
        </section>
      )}

      <section style={sectionStyle}>
        <h2 style={sectionTitleStyle}>{t("mobile.passport.unit")}</h2>
        {unit ? <UnitView unit={unit} t={t} /> : <p>{t("mobile.passport.no_unit")}</p>}
      </section>

      {passport.points && passport.points.length > 0 && (
        <section style={sectionStyle}>
          <h2 style={sectionTitleStyle}>{t("mobile.passport.latest")}</h2>
          {passport.points.map((point) => (
            <p key={point.id}>
              {point.name} —{" "}
              {point.latest
                ? `${formatNumber(locale, point.latest.value)} ${point.unit} (${formatDateTime(
                    locale,
                    point.latest.measured_at,
                    timeZone,
                  )})`
                : t("mobile.passport.no_measurement")}
              {point.latest && point.latest.quality_flags.length > 0
                ? ` — ${t("mobile.passport.flagged")}`
                : ""}
            </p>
          ))}
        </section>
      )}

      <section style={sectionStyle}>
        <h2 style={sectionTitleStyle}>{t("mobile.passport.signals")}</h2>
        {alarms.map((alarm) => (
          <p key={alarm.id}>
            {t("mobile.passport.alarm")} · {t(`severity.${alarm.severity}`)} ·{" "}
            {t(`condition_state.${alarm.condition_state}`)} · {t(`ack_state.${alarm.ack_state}`)}
            <br />
            {alarm.message}
          </p>
        ))}
        {passport.open_findings.map((finding) => (
          <p key={finding.id}>
            {t("mobile.passport.finding")} · {t(`severity.${finding.severity}`)} ·{" "}
            {t(`certainty.${finding.certainty}`)} · {t(`condition_state.${finding.condition_state}`)}
            <br />
            {finding.title}
          </p>
        ))}
        {alarms.length === 0 && passport.open_findings.length === 0 && (
          <p>{t("mobile.passport.nothing_open")}</p>
        )}
      </section>

      {passport.open_work_orders && passport.open_work_orders.length > 0 && (
        <section style={sectionStyle}>
          <h2 style={sectionTitleStyle}>{t("mobile.passport.work_orders")}</h2>
          {passport.open_work_orders.map((order) => (
            <p key={order.id}>
              {order.title} ({t(`work_order.status.${order.status}`)})
            </p>
          ))}
        </section>
      )}

      {passport.recent_interventions && passport.recent_interventions.length > 0 && (
        <section style={sectionStyle}>
          <h2 style={sectionTitleStyle}>{t("mobile.passport.interventions")}</h2>
          {passport.recent_interventions.map((item) => (
            <p key={item.id}>
              {formatDate(locale, item.started_at, timeZone)} —{" "}
              {item.action_label ?? item.summary ?? t("mobile.passport.no_summary")}
              {item.symptom_label ? ` (${item.symptom_label})` : ""}
            </p>
          ))}
        </section>
      )}

      <p style={mutedStyle}>
        {timeZone
          ? t("mobile.passport.site_time", { timezone: timeZone })
          : t("mobile.passport.device_time")}
      </p>
    </main>
  );
}

function StatusLine({
  status,
  timeZone,
  locale,
  t,
}: {
  status: EquipmentStatus;
  timeZone: string | null;
  locale: Locale;
  t: (key: string, params?: Record<string, string>) => string;
}) {
  const { key, params } = statusMessage(status);
  const rendered = Object.fromEntries(
    Object.entries(params ?? {}).map(([name, value]) => [
      name,
      name === "since" ? formatDateTime(locale, value, timeZone) : t(value),
    ]),
  );
  return <p style={status.current ? strongStyle : undefined}>{t(key, rendered)}</p>;
}

function UnitView({
  unit,
  t,
}: {
  unit: PassportUnit;
  t: (key: string, params?: Record<string, string>) => string;
}) {
  return (
    <>
      <p style={strongStyle}>
        {unit.manufacturer} {unit.reference}
      </p>
      <p>{t("mobile.passport.equipment_type", { type: t(`equipment_type.${unit.equipment_type}`) })}</p>
      {unit.manufacturer_designation && <p style={mutedStyle}>{unit.manufacturer_designation}</p>}
      <p>{t("mobile.passport.serial", { serial: unit.serial_number })}</p>
      {unit.asset_code && <p>{t("mobile.passport.asset_code", { code: unit.asset_code })}</p>}
      <p>{t("mobile.passport.state", { state: t(`lifecycle.${unit.lifecycle_state}`) })}</p>
    </>
  );
}
