
import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  Activity,
  BarChart3,
  BrainCircuit,
  Camera,
  AlertTriangle,
  BellRing,
  ChevronDown,
  ChevronRight,
  CircleUserRound,
  Eye,
  EyeOff,
  Gauge,
  History,
  Info,
  LogOut,
  Menu,
  Play,
  RefreshCcw,
  ShieldCheck,
  Square,
  Video,
  X,
} from "lucide-react";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import "./App.css";
import { supabase } from "./supabaseClient";


const API_BASE =
  import.meta.env.VITE_API_BASE ||
  "http://127.0.0.1:8000";

const WS_BASE =
  import.meta.env.VITE_WS_BASE ||
  "ws://127.0.0.1:8000";


function getToken() {
  return sessionStorage.getItem("nino_token");
}


function authHeaders() {
  const token = getToken();

  return token
    ? {
        Authorization: `Bearer ${token}`,
      }
    : {};
}


function titleCaseName(value = "") {
  return String(value)
    .trim()
    .toLowerCase()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}


function formatDriveDuration(value) {
  const total = Math.max(0, Math.round(Number(value) || 0));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;

  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }

  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}


function formatSessionDate(value) {
  if (!value) return "Unknown date";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Unknown date";
  }

  return new Intl.DateTimeFormat(undefined, {
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}


function buildAttentionSeries(samples = []) {
  if (!Array.isArray(samples) || samples.length === 0) {
    return [];
  }

  const firstTimestamp = new Date(
    samples[0]?.captured_at || 0
  ).getTime();

  return samples.map((sample, index) => {
    const capturedAt = new Date(
      sample?.captured_at || 0
    ).getTime();

    const elapsed =
      Number.isFinite(capturedAt) &&
      Number.isFinite(firstTimestamp)
        ? Math.max(
            0,
            (capturedAt - firstTimestamp) / 1000
          )
        : index;

    const alertState = String(
      sample?.alert_state || ""
    ).toUpperCase();

    const distractionState = String(
      sample?.distraction_state || ""
    ).toUpperCase();

    const eyeState = String(
      sample?.eye_state || ""
    ).toUpperCase();

    let attention = 100;

    if (
      alertState.includes("CRITICAL_DROWSINESS")
      ||
      eyeState.includes("DROWS")
    ) {
      attention = 5;
    } else if (
      alertState.includes("CRITICAL_DISTRACTION")
      ||
      distractionState.startsWith("DISTRACTED_")
    ) {
      attention = 20;
    } else if (
      alertState.includes("EARLY_")
      ||
      distractionState.startsWith("WARNING_")
    ) {
      attention = 55;
    } else if (
      distractionState.startsWith("LOOKING_")
    ) {
      attention = 75;
    }

    return {
      elapsed:
        Number(elapsed.toFixed(1)),
      attention,
      ear:
        Number(sample?.ear || 0),
      mar:
        Number(sample?.mar || 0),
      direction:
        sample?.head_direction || "UNKNOWN",
      alert:
        sample?.alert_state || "NORMAL",
    };
  });
}


function formatElapsedSeconds(value) {
  const seconds = Math.max(
    0,
    Number(value) || 0
  );

  if (seconds < 60) {
    return `${seconds.toFixed(1)}s`;
  }

  const minutes = Math.floor(seconds / 60);
  const remaining = Math.floor(seconds % 60);

  return `${minutes}:${String(remaining).padStart(2, "0")}`;
}


function parseAuthHashIssue() {
  const rawHash = window.location.hash.replace(/^#/, "");

  if (!rawHash) return null;

  const params = new URLSearchParams(rawHash);
  const error = params.get("error");
  const errorCode = params.get("error_code");
  const description = params.get("error_description");

  if (!error && !errorCode) return null;

  if (errorCode === "otp_expired") {
    return {
      code: "otp_expired",
      message: "This confirmation link has expired. Enter your email below and request a new confirmation email.",
      canResend: true,
    };
  }

  return {
    code: errorCode || error || "auth_error",
    message: description
      ? decodeURIComponent(description.replace(/\+/g, " "))
      : "This authentication link is no longer valid. Please request a new one.",
    canResend: true,
  };
}


function createEmptyLiveState() {
  return {
    connected: false,
    drive_active: false,
    session_id: null,
    face_detected: false,
    ear: null,
    mar: null,
    eye_state: "UNKNOWN",
    head_direction: "UNKNOWN",
    head_direction_confidence: null,
    head_direction_probabilities: {},
    distraction_state: "UNKNOWN",
    distraction_duration: 0,
    alert_state: "IDLE",
    events: [],
    calibrated: false,
    calibration_progress: 0,
    calibration: {
      active: false,
      progress: 0,
      percent: 0,
      message: "Start a drive to calibrate",
    },
    landmark_overlay: {},
    performance: {
      ai_fps: 0,
      inference_ms: 0,
    },
  };
}


/* =========================================================
   LOGIN
========================================================= */

function Login({
  onLogin,
  authIssue = null,
  onClearAuthIssue = () => {},
  passwordRecovery = false,
  onRecoveryComplete = () => {},
}) {
  const [mode, setMode] = useState("signin");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);
  const [checkInbox, setCheckInbox] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const cleanEmail = email.trim().toLowerCase();
  const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(cleanEmail);
  const passwordRules = {
    length: password.length >= 8,
    letter: /[A-Za-z]/.test(password),
    number: /\d/.test(password),
  };
  const strongEnough = Object.values(passwordRules).every(Boolean);
  const passwordsMatch = password === confirmPassword && confirmPassword.length > 0;

  function clearFeedback() {
    setError("");
    setMessage("");
    setSubmitted(false);
    onClearAuthIssue();
  }

  useEffect(() => {
    if (!authIssue) return;
    setMode("signin");
    setCheckInbox(false);
    setError(authIssue.message || "");
    setMessage("");
  }, [authIssue]);

  useEffect(() => {
    if (resendCooldown <= 0) return undefined;
    const timer = window.setInterval(() => {
      setResendCooldown((current) => Math.max(0, current - 1));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [resendCooldown]);

  async function loadBackendUser(accessToken) {
    sessionStorage.setItem("nino_token", accessToken);
    const response = await fetch(`${API_BASE}/api/auth/me`, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    });

    let data = {};
    try {
      data = await response.json();
    } catch {
      data = {};
    }

    if (!response.ok) {
      throw new Error(data.detail || "NINO backend authentication failed.");
    }

    onLogin({
      ...data,
      name: titleCaseName(data.name || data.email?.split("@")[0] || "NINO User"),
    });
  }

  async function resendConfirmation() {
    if (!emailValid) {
      setSubmitted(true);
      setError("Enter the email address you registered with first.");
      return;
    }

    if (resendCooldown > 0 || busy) return;

    setBusy(true);
    setError("");
    setMessage("");

    try {
      const { error: resendError } = await supabase.auth.resend({
        type: "signup",
        email: cleanEmail,
        options: {
          emailRedirectTo: window.location.origin,
        },
      });

      if (resendError) throw resendError;

      setResendCooldown(30);
      setMessage("Confirmation email sent. Check your inbox and spam folder.");
      setCheckInbox(true);
      onClearAuthIssue();
    } catch {
      setError("We couldn't resend the confirmation email right now. Please try again shortly.");
    } finally {
      setBusy(false);
    }
  }

  async function sendPasswordReset() {
    if (!emailValid) {
      setSubmitted(true);
      setError("Enter a valid email address first.");
      return;
    }

    setBusy(true);
    setError("");
    setMessage("");

    try {
      const { error: resetError } = await supabase.auth.resetPasswordForEmail(
        cleanEmail,
        { redirectTo: window.location.origin }
      );

      if (resetError) throw resetError;

      setMessage(
        "If an account exists for this email, a password reset link has been sent."
      );
    } catch {
      setError("We couldn't send a reset link right now. Please try again shortly.");
    } finally {
      setBusy(false);
    }
  }

  async function submit(event) {
    event.preventDefault();
    setSubmitted(true);
    setError("");
    setMessage("");

    if (!passwordRecovery && !emailValid) {
      setError("Enter a valid email address.");
      return;
    }

    if (passwordRecovery) {
      if (!strongEnough) {
        setError("Your new password must meet all password requirements.");
        return;
      }
      if (!passwordsMatch) {
        setError("Passwords do not match.");
        return;
      }
    }

    if (mode === "signup" && !passwordRecovery) {
      if (!fullName.trim()) {
        setError("Enter your full name.");
        return;
      }
      if (!strongEnough) {
        setError("Your password must meet all password requirements.");
        return;
      }
      if (!passwordsMatch) {
        setError("Passwords do not match.");
        return;
      }
    }

    if (mode === "signin" && !passwordRecovery && password.length < 6) {
      setError("Enter your password.");
      return;
    }

    setBusy(true);

    try {
      if (passwordRecovery) {
        const { error: updateError } = await supabase.auth.updateUser({ password });
        if (updateError) throw updateError;

        const { data: sessionData } = await supabase.auth.getSession();
        if (sessionData.session?.access_token) {
          await loadBackendUser(sessionData.session.access_token);
        }

        onRecoveryComplete();
        setPassword("");
        setConfirmPassword("");
        return;
      }

      if (mode === "signup") {
        const { data, error: signUpError } = await supabase.auth.signUp({
          email: cleanEmail,
          password,
          options: {
            data: {
              full_name: titleCaseName(fullName),
              role: "Driver",
            },
            emailRedirectTo: window.location.origin,
          },
        });

        if (signUpError) throw signUpError;

        if (!data.session) {
          setCheckInbox(true);
          setResendCooldown(30);
          setPassword("");
          setConfirmPassword("");
          return;
        }

        await loadBackendUser(data.session.access_token);
        return;
      }

      const { data, error: signInError } = await supabase.auth.signInWithPassword({
        email: cleanEmail,
        password,
      });

      if (signInError) {
        if (/email not confirmed/i.test(signInError.message || "")) {
          setError(
            "Your email is not confirmed yet. Check your inbox or resend the confirmation email below."
          );
        } else {
          setError(
            "We couldn't sign you in. Check your email and password, then try again."
          );
        }
        return;
      }

      if (!data.session) {
        setError("We couldn't sign you in. Please try again.");
        return;
      }

      await loadBackendUser(data.session.access_token);
    } catch (authError) {
      if (mode === "signup") {
        setError(
          authError?.message || "We couldn't create your account. Please try again."
        );
      } else {
        setError("We couldn't sign you in. Check your details and try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  function changeMode(nextMode) {
    setMode(nextMode);
    setCheckInbox(false);
    setError("");
    setMessage("");
    setSubmitted(false);
    setPassword("");
    setConfirmPassword("");
    onClearAuthIssue();
  }

  const canResend =
    Boolean(authIssue?.canResend) ||
    /email.*not confirmed|confirm.*email|confirmation link.*expired|link.*expired/i.test(error);

  if (checkInbox && !passwordRecovery) {
    return (
      <div className="auth-shell auth-shell-compact">
        <section className="auth-hero">
          <div className="auth-brand">
            <div className="logo-mark">N</div>
            <div>
              <strong>NINO</strong>
              <span>Driver Safety Intelligence</span>
            </div>
          </div>

          <div className="auth-copy">
            <span className="kicker">AI DRIVER SAFETY</span>
            <h1>Safer driving starts with attention.</h1>
            <p>
              Real-time driver monitoring, intelligent warnings and personal
              safety analytics in one secure experience.
            </p>
          </div>
        </section>

        <section className="auth-panel">
          <div className="auth-card auth-inbox-card">
            <div className="auth-inbox-icon">
              <ShieldCheck size={28} />
            </div>
            <span className="kicker">EMAIL CONFIRMATION</span>
            <h2>Check your inbox</h2>
            <p>
              We sent a confirmation link to <strong>{cleanEmail}</strong>.
              Open it to activate your NINO account.
            </p>

            <div className="auth-inbox-note">
              Didn't receive it? Check your spam or junk folder first.
            </div>

            {message && <div className="auth-success" role="status">{message}</div>}
            {error && <div className="auth-error" role="alert">{error}</div>}

            <button
              type="button"
              className="btn primary wide"
              onClick={() => window.open("https://mail.google.com/", "_blank", "noopener,noreferrer")}
            >
              Open Gmail
            </button>

            <button
              type="button"
              className="auth-text-button auth-text-button-centered"
              onClick={resendConfirmation}
              disabled={busy || resendCooldown > 0}
            >
              {resendCooldown > 0
                ? `Resend available in ${resendCooldown}s`
                : "Resend confirmation email"}
            </button>

            <button
              type="button"
              className="auth-text-button auth-text-button-muted auth-text-button-centered"
              onClick={() => changeMode("signin")}
            >
              Back to sign in
            </button>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="auth-shell auth-shell-compact">
      <section className="auth-hero">
        <div className="auth-brand">
          <div className="logo-mark">N</div>
          <div>
            <strong>NINO</strong>
            <span>Driver Safety Intelligence</span>
          </div>
        </div>

        <div className="auth-copy">
          <span className="kicker">AI DRIVER SAFETY</span>
          <h1>Intelligence that watches the road with you.</h1>
          <p>
            Real-time driver monitoring, intelligent warnings and personal
            safety analytics — designed to keep attention where it matters.
          </p>

          <div className="auth-feature-grid">
            <article>
              <Camera size={18} />
              <div>
                <strong>Live monitoring</strong>
                <span>Fast browser-native camera preview</span>
              </div>
            </article>
            <article>
              <BrainCircuit size={18} />
              <div>
                <strong>AI driver state</strong>
                <span>Head direction and attention signals</span>
              </div>
            </article>
            <article>
              <ShieldCheck size={18} />
              <div>
                <strong>Private by design</strong>
                <span>Video is processed live and never stored</span>
              </div>
            </article>
          </div>

          <div className="auth-product-preview" aria-hidden="true">
            <div className="auth-preview-top">
              <span className="auth-preview-dot" />
              <strong>Live safety preview</strong>
              <span>AI ready</span>
            </div>

            <div className="auth-preview-screen">
              <div className="auth-preview-face">
                <span className="auth-preview-eye left" />
                <span className="auth-preview-eye right" />
                <span className="auth-preview-mouth" />
              </div>

              <div className="auth-preview-stats">
                <span>Eyes <strong>OPEN</strong></span>
                <span>Attention <strong>FORWARD</strong></span>
                <span>Status <strong>SAFE</strong></span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="auth-panel">
        <form className="auth-card" onSubmit={submit} noValidate>
          <span className="kicker">NINO ACCOUNT</span>

          <h2>
            {passwordRecovery
              ? "Choose a new password"
              : mode === "signup"
              ? "Create your account"
              : "Sign in to NINO"}
          </h2>

          <p>
            {passwordRecovery
              ? "Choose a strong password for your NINO account."
              : mode === "signup"
              ? "Create your profile and start building your personal drive history."
              : "Pick up where you left off and start your next drive."}
          </p>

          {!passwordRecovery && (
            <div className="auth-tabs" role="tablist" aria-label="Authentication mode">
              <button
                type="button"
                role="tab"
                aria-selected={mode === "signin"}
                className={mode === "signin" ? "active" : ""}
                onClick={() => changeMode("signin")}
              >
                Sign in
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={mode === "signup"}
                className={mode === "signup" ? "active" : ""}
                onClick={() => changeMode("signup")}
              >
                Register
              </button>
            </div>
          )}

          {!passwordRecovery && mode === "signup" && (
            <label>
              Full name
              <input
                type="text"
                autoComplete="name"
                value={fullName}
                onChange={(event) => {
                  setFullName(event.target.value);
                  clearFeedback();
                }}
                placeholder="Your full name"
              />
              {submitted && !fullName.trim() && (
                <small className="field-error">Enter your full name.</small>
              )}
            </label>
          )}

          {!passwordRecovery && (
            <label>
              Email
              <input
                type="email"
                inputMode="email"
                autoComplete="email"
                autoFocus
                value={email}
                onChange={(event) => {
                  setEmail(event.target.value);
                  clearFeedback();
                }}
                placeholder="you@example.com"
                aria-invalid={submitted && !emailValid}
              />
              {submitted && !emailValid && (
                <small className="field-error">Enter a valid email address.</small>
              )}
            </label>
          )}

          <label>
            {passwordRecovery ? "New password" : "Password"}
            <div className="password-field">
              <input
                type={showPassword ? "text" : "password"}
                autoComplete={
                  passwordRecovery || mode === "signup"
                    ? "new-password"
                    : "current-password"
                }
                value={password}
                onChange={(event) => {
                  setPassword(event.target.value);
                  clearFeedback();
                }}
                placeholder={
                  passwordRecovery || mode === "signup"
                    ? "Create a strong password"
                    : "Enter your password"
                }
              />
              <button
                type="button"
                className="password-toggle"
                aria-label={showPassword ? "Hide password" : "Show password"}
                onClick={() => setShowPassword((current) => !current)}
              >
                {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
              </button>
            </div>
          </label>

          {(passwordRecovery || mode === "signup") && (
            <div className="password-rules" aria-live="polite">
              <span className={passwordRules.length ? "met" : ""}>8+ characters</span>
              <span className={passwordRules.letter ? "met" : ""}>Letter</span>
              <span className={passwordRules.number ? "met" : ""}>Number</span>
            </div>
          )}

          {(passwordRecovery || mode === "signup") && (
            <label>
              Confirm password
              <input
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(event) => {
                  setConfirmPassword(event.target.value);
                  clearFeedback();
                }}
                placeholder="Repeat password"
                aria-invalid={submitted && !passwordsMatch}
              />
              {submitted && confirmPassword && !passwordsMatch && (
                <small className="field-error">Passwords do not match.</small>
              )}
            </label>
          )}

          {!passwordRecovery && mode === "signin" && (
            <div className="auth-inline-actions">
              <span className="auth-trust-line">Video is processed live and never stored.</span>
              <button
                type="button"
                className="auth-text-button"
                onClick={sendPasswordReset}
                disabled={busy}
              >
                Forgot password?
              </button>
            </div>
          )}

          {error && (
            <div className="auth-error" role="alert" aria-live="assertive">
              <AlertTriangle size={18} />
              <div className="auth-error-copy">
                <span>{error}</span>
                {canResend && (
                  <button
                    type="button"
                    className="auth-text-button auth-error-action"
                    onClick={resendConfirmation}
                    disabled={busy || resendCooldown > 0}
                  >
                    {resendCooldown > 0
                      ? `Resend in ${resendCooldown}s`
                      : "Resend confirmation email"}
                  </button>
                )}
              </div>
            </div>
          )}

          {message && (
            <div className="auth-success" role="status" aria-live="polite">
              {message}
            </div>
          )}

          <button className="btn primary wide auth-submit" disabled={busy}>
            {busy && <span className="button-spinner" aria-hidden="true" />}
            {busy
              ? "Please wait..."
              : passwordRecovery
              ? "Save new password"
              : mode === "signup"
              ? "Create account"
              : "Log in"}
          </button>

          {!passwordRecovery && mode === "signup" && (
            <div className="auth-trust-footer">
              By creating an account, you can securely save your personal drive history.
              Camera video itself is not stored by NINO.
            </div>
          )}
        </form>
      </section>
    </div>
  );
}

/* =========================================================
   SMALL UI COMPONENTS
========================================================= */

function StatCard({
  icon,
  label,
  value,
  helper,
  tone = "neutral",
}) {
  return (
    <article
      className={`stat-card ${tone}`}
    >
      <div className="stat-icon">
        {icon}
      </div>

      <div className="stat-content">
        <div className="stat-label-row">
          <span className="stat-label">
            {label}
          </span>

          {helper && (
            <span
              className="metric-info"
              tabIndex={0}
              aria-label={`${label}: ${helper}`}
            >
              <Info size={13} />

              <span className="metric-tooltip">
                {helper}
              </span>
            </span>
          )}
        </div>

        <strong className="stat-value">
          {value}
        </strong>
      </div>
    </article>
  );
}


function SectionTitle({
  eyebrow,
  title,
  action,
}) {
  return (
    <div className="section-title">

      <div>
        <span className="kicker">
          {eyebrow}
        </span>

        <h2>
          {title}
        </h2>
      </div>

      {action}

    </div>
  );
}



function LandmarkOverlay({
  overlay,
  faceDetected,
}) {
  if (
    !faceDetected
    ||
    !overlay
    ||
    Object.keys(overlay).length === 0
  ) {
    return null;
  }

  const groups = [
    {
      key: "face",
      stroke: "rgba(53, 226, 158, 0.62)",
      fill: "rgba(53, 226, 158, 0.88)",
      radius: 0.9,
      width: 0.75,
      close: true,
    },
    {
      key: "left_eye",
      stroke: "rgba(106, 224, 255, 0.95)",
      fill: "rgba(106, 224, 255, 1)",
      radius: 1.05,
      width: 0.95,
      close: true,
    },
    {
      key: "right_eye",
      stroke: "rgba(106, 224, 255, 0.95)",
      fill: "rgba(106, 224, 255, 1)",
      radius: 1.05,
      width: 0.95,
      close: true,
    },
    {
      key: "mouth",
      stroke: "rgba(255, 191, 87, 0.98)",
      fill: "rgba(255, 191, 87, 1)",
      radius: 0.95,
      width: 0.9,
      close: true,
    },
    {
      key: "nose",
      stroke: "rgba(255, 255, 255, 0.9)",
      fill: "rgba(255, 255, 255, 1)",
      radius: 0.95,
      width: 0.85,
      close: false,
    },
  ];

  function makePath(
    points,
    close
  ) {
    if (
      !Array.isArray(points)
      ||
      points.length === 0
    ) {
      return "";
    }

    return (
      points
        .map(
          (
            point,
            index
          ) =>
            `${
              index === 0
                ? "M"
                : "L"
            } ${
              Number(point.x) * 100
            } ${
              Number(point.y) * 100
            }`
        )
        .join(" ")
      +
      (
        close
          ? " Z"
          : ""
      )
    );
  }

  return (
    <svg
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      aria-hidden="true"
      style={{
        position: "absolute",
        inset: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none",
        zIndex: 5,
      }}
    >
      {groups.map(
        (
          group
        ) => {
          const points =
            overlay[
              group.key
            ]
            ||
            [];

          if (
            !points.length
          ) {
            return null;
          }

          return (
            <g
              key={
                group.key
              }
            >
              <path
                d={
                  makePath(
                    points,
                    group.close
                  )
                }
                fill="none"
                stroke={
                  group.stroke
                }
                strokeWidth={
                  group.width
                }
                vectorEffect="non-scaling-stroke"
              />

              {points.map(
                (
                  point,
                  index
                ) => (
                  <circle
                    key={
                      `${group.key}-${index}`
                    }
                    cx={
                      Number(
                        point.x
                      ) * 100
                    }
                    cy={
                      Number(
                        point.y
                      ) * 100
                    }
                    r={
                      group.radius
                    }
                    fill={
                      group.fill
                    }
                  />
                )
              )}
            </g>
          );
        }
      )}
    </svg>
  );
}


function LivePerformanceHud({
  performance,
  faceDetected,
}) {
  const fps =
    Number(
      performance
        ?.ai_fps
      ||
      0
    );

  const latency =
    Number(
      performance
        ?.inference_ms
      ||
      0
    );

  return (
    <div
      style={{
        position: "absolute",
        top: "12px",
        left: "12px",
        zIndex: 7,
        display: "flex",
        flexWrap: "wrap",
        gap: "6px",
        pointerEvents: "none",
      }}
    >
      <span
        style={{
          padding: "6px 9px",
          borderRadius: "999px",
          background: "rgba(10, 25, 20, 0.78)",
          color: faceDetected
            ? "#89f1c5"
            : "#d8dfdc",
          fontSize: "10px",
          fontWeight: 800,
          letterSpacing: ".06em",
          backdropFilter: "blur(8px)",
        }}
      >
        {faceDetected
          ? "● FACE TRACKING"
          : "○ SEARCHING FACE"}
      </span>

      <span
        style={{
          padding: "6px 9px",
          borderRadius: "999px",
          background: "rgba(10, 25, 20, 0.78)",
          color: "#fff",
          fontSize: "10px",
          fontWeight: 700,
          backdropFilter: "blur(8px)",
        }}
      >
        AI {fps.toFixed(1)} FPS
      </span>

      <span
        style={{
          padding: "6px 9px",
          borderRadius: "999px",
          background: "rgba(10, 25, 20, 0.78)",
          color:
            latency > 150
              ? "#ffc56c"
              : "#fff",
          fontSize: "10px",
          fontWeight: 700,
          backdropFilter: "blur(8px)",
        }}
      >
        {latency.toFixed(0)} ms
      </span>
    </div>
  );
}



function HeadDirectionArrow({
  direction,
  visible,
}) {
  if (!visible) {
    return null;
  }

  const normalized =
    String(
      direction
      ||
      "FORWARD"
    ).toUpperCase();

  const arrows = {
    FORWARD: "↑",
    LEFT: "←",
    RIGHT: "→",
    UP: "↑",
    DOWN: "↓",
  };

  const arrow =
    arrows[
      normalized
    ]
    ||
    "•";

  return (
    <div
      className="head-direction-hud"
      aria-hidden="true"
    >
      <span className="head-direction-arrow">
        {arrow}
      </span>

      <small>
        {
          normalized.replaceAll(
            "_",
            " "
          )
        }
      </small>
    </div>
  );
}


function CalibrationOverlay({
  calibration,
  calibrated,
  driveActive,
}) {
  if (!driveActive) {
    return null;
  }

  const active = Boolean(
    calibration?.active
  );

  const percent = Number(
    calibration?.percent || 0
  );

  if (!active && calibrated) {
    return (
      <div
        style={{
          position: "absolute",
          bottom: "14px",
          left: "50%",
          transform: "translateX(-50%)",
          zIndex: 12,
          padding: "7px 12px",
          borderRadius: "999px",
          background: "rgba(12, 83, 58, 0.88)",
          color: "#ffffff",
          fontSize: "11px",
          fontWeight: 800,
          letterSpacing: ".04em",
          pointerEvents: "none",
        }}
      >
        ✓ CALIBRATED
      </div>
    );
  }

  if (!active) {
    return null;
  }

  const remaining = Math.max(
    1,
    Math.ceil(
      (100 - percent) / 34
    )
  );

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        zIndex: 11,
        display: "grid",
        placeItems: "center",
        padding: "24px",
        background: "rgba(5, 18, 14, 0.68)",
        backdropFilter: "blur(2px)",
        color: "#ffffff",
        textAlign: "center",
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          width: "min(340px, 90%)",
          padding: "24px",
          borderRadius: "18px",
          background: "rgba(12, 32, 25, 0.88)",
          border: "1px solid rgba(125, 239, 193, 0.25)",
          boxShadow: "0 18px 60px rgba(0,0,0,.28)",
        }}
      >
        <div
          style={{
            width: "72px",
            height: "72px",
            margin: "0 auto 14px",
            borderRadius: "50%",
            border: "3px solid rgba(121, 237, 190, .35)",
            display: "grid",
            placeItems: "center",
            fontSize: "32px",
            fontWeight: 800,
            color: "#82f0c0",
          }}
        >
          {remaining}
        </div>

        <strong
          style={{
            display: "block",
            fontSize: "18px",
            marginBottom: "7px",
          }}
        >
          Look straight ahead
        </strong>

        <p
          style={{
            margin: 0,
            color: "#bed0c8",
            fontSize: "12px",
            lineHeight: 1.5,
          }}
        >
          Keep your head still while NINO learns your neutral driving position.
        </p>

        <div
          style={{
            width: "100%",
            height: "7px",
            marginTop: "18px",
            overflow: "hidden",
            borderRadius: "999px",
            background: "rgba(255,255,255,.12)",
          }}
        >
          <div
            style={{
              width: `${percent}%`,
              height: "100%",
              borderRadius: "999px",
              background: "#53d69f",
              transition: "width .15s ease",
            }}
          />
        </div>

        <small
          style={{
            display: "block",
            marginTop: "8px",
            color: "#a7bcb3",
            fontSize: "10px",
          }}
        >
          Calibrating {percent}%
        </small>
      </div>
    </div>
  );
}


/* =========================================================
   MAIN APP
========================================================= */

function App() {
  const [user, setUser] =
    useState(null);

  const [page, setPage] =
    useState("dashboard");

  const [sidebarOpen, setSidebarOpen] =
    useState(false);

  const [profileOpen, setProfileOpen] =
    useState(false);

  const [profileName, setProfileName] =
    useState("");

  const [profilePhone, setProfilePhone] =
    useState("");

  const [profileSaving, setProfileSaving] =
    useState(false);

  const [profileMessage, setProfileMessage] =
    useState("");

  const [summary, setSummary] =
    useState(null);

  const [sessions, setSessions] =
    useState([]);

  const [modelInfo, setModelInfo] =
    useState(null);

  const [notice, setNotice] =
    useState("");

  const [cameraReady, setCameraReady] =
    useState(false);

  const [socketReady, setSocketReady] =
    useState(false);

  const [driveSeconds, setDriveSeconds] =
    useState(0);

  const [liveState, setLiveState] =
    useState(
      createEmptyLiveState()
    );

  const [liveSeries, setLiveSeries] =
    useState([]);

  const [authIssue, setAuthIssue] =
    useState(null);

  const [passwordRecovery, setPasswordRecovery] =
    useState(false);

  const [historyQuery, setHistoryQuery] =
    useState("");

  const [historySort, setHistorySort] =
    useState("newest");

  const [sessionDetail, setSessionDetail] =
    useState(null);

  const [sessionLoading, setSessionLoading] =
    useState(false);

  const [alertFlash, setAlertFlash] =
    useState(false);


  /* =====================================================
     REFS
  ===================================================== */

  const videoRef = useRef(null);
  const canvasRef = useRef(null);

  const streamRef = useRef(null);

  const socketRef = useRef(null);

  const sendLoopRef = useRef(null);

  const waitingForInferenceRef =
    useRef(false);

  const driveTimerRef =
    useRef(null);

  const lastCriticalAlertRef =
    useRef("");


  /* =====================================================
     API REQUEST HELPER
  ===================================================== */

  async function request(
    path,
    options = {}
  ) {
    const response =
      await fetch(
        `${API_BASE}${path}`,
        {
          ...options,

          headers: {
            ...authHeaders(),
            ...(options.headers || {}),
          },
        }
      );

    let data = {};

    try {
      data =
        await response.json();
    } catch {
      data = {};
    }

    if (!response.ok) {
      throw new Error(
        data.detail ||
        "Request failed."
      );
    }

    return data;
  }


  /* =====================================================
     BACKEND DATA
  ===================================================== */

  async function loadSummary() {
    try {
      const data =
        await request(
          "/api/sessions/latest"
        );

      setSummary(data);

    } catch (error) {
      if (
        !String(
          error.message
        ).includes(
          "No analyzed"
        )
      ) {
        console.error(error);
      }
    }
  }


  async function loadSessions() {
    try {
      const data =
        await request(
          "/api/sessions"
        );

      setSessions(
        data.sessions || []
      );

    } catch (error) {
      console.error(error);
    }
  }


  async function loadModelInfo() {
    try {
      const data =
        await request(
          "/api/model/info"
        );

      setModelInfo(data);

    } catch (error) {
      console.error(error);
    }
  }


  async function openSession(
    sessionId
  ) {
    setSessionLoading(true);
    setSessionDetail(null);

    try {
      const data =
        await request(
          `/api/sessions/${sessionId}`
        );

      setSessionDetail(data);

    } catch (error) {
      setNotice(
        error.message
      );
    } finally {
      setSessionLoading(false);
    }
  }


  async function bootstrap() {
    try {
      const {
        data,
        error,
      } = await supabase.auth
        .getSession();

      if (error) {
        throw error;
      }

      const session =
        data.session;

      if (!session) {
        sessionStorage.removeItem(
          "nino_token"
        );

        setUser(null);
        return;
      }

      sessionStorage.setItem(
        "nino_token",
        session.access_token
      );

      const me =
        await request(
          "/api/auth/me"
        );

      setUser(me);

      await Promise.all([
        loadSummary(),
        loadSessions(),
        loadModelInfo(),
      ]);

    } catch (error) {
      console.error(
        "NINO auth bootstrap:",
        error
      );

      sessionStorage.removeItem(
        "nino_token"
      );

      setUser(null);
    }
  }


  /* =====================================================
     BROWSER CAMERA
  ===================================================== */

  async function attachStreamToVideo() {
    const video =
      videoRef.current;

    const stream =
      streamRef.current;

    if (
      !video
      ||
      !stream
    ) {
      return;
    }

    if (
      video.srcObject
      !==
      stream
    ) {
      video.srcObject =
        stream;
    }

    try {
      await video.play();
    } catch {
      // Autoplay may briefly wait until DOM is ready.
    }
  }


  async function startBrowserCamera() {
    if (
      streamRef.current
    ) {
      setCameraReady(true);
      return;
    }

    if (
      !navigator.mediaDevices
      ||
      !navigator.mediaDevices
        .getUserMedia
    ) {
      throw new Error(
        "Browser camera access is not supported."
      );
    }

    const stream =
      await navigator.mediaDevices
        .getUserMedia({
          video: {
            width: {
              ideal: 1280,
            },

            height: {
              ideal: 720,
            },

            frameRate: {
              ideal: 30,
              max: 30,
            },

            facingMode:
              "user",
          },

          audio: false,
        });

    streamRef.current =
      stream;

    setCameraReady(true);
  }


  function stopBrowserCamera() {
    if (
      streamRef.current
    ) {
      streamRef.current
        .getTracks()
        .forEach(
          (track) =>
            track.stop()
        );
    }

    streamRef.current =
      null;

    if (
      videoRef.current
    ) {
      videoRef.current.srcObject =
        null;
    }

    setCameraReady(false);
  }


  /*
   * IMPORTANT:
   * The video element does not exist until cameraReady
   * renders it. It can also be replaced when moving
   * Dashboard → Live Monitor. Re-attach the same MediaStream
   * whenever the rendered video element changes.
   */
  useEffect(
    () => {
      if (cameraReady) {
        attachStreamToVideo();
      }
    },
    [
      cameraReady,
      page,
    ]
  );


  /* =====================================================
     WEBSOCKET
  ===================================================== */

  function closeWebSocket() {
    waitingForInferenceRef.current =
      false;

    if (
      sendLoopRef.current
    ) {
      clearInterval(
        sendLoopRef.current
      );

      sendLoopRef.current =
        null;
    }

    if (
      socketRef.current
    ) {
      try {
        socketRef.current.close();
      } catch {
        // ignore
      }
    }

    socketRef.current =
      null;

    setSocketReady(false);
  }


  function sendFrame() {
    const socket =
      socketRef.current;

    const video =
      videoRef.current;

    const canvas =
      canvasRef.current;

    /*
     * Do not use cameraReady state here.
     *
     * The interval is intentionally based on refs so it
     * cannot get stuck with a stale React-state closure.
     */
    if (
      !socket
      ||
      socket.readyState
      !==
      WebSocket.OPEN
      ||
      !streamRef.current
      ||
      !video
      ||
      !canvas
      ||
      waitingForInferenceRef.current
      ||
      video.readyState < 2
    ) {
      return;
    }

    const width = 640;

    const videoWidth =
      video.videoWidth || 1280;

    const videoHeight =
      video.videoHeight || 720;

    const height =
      Math.round(
        width
        *
        videoHeight
        /
        videoWidth
      );

    canvas.width =
      width;

    canvas.height =
      height;

    const context =
      canvas.getContext(
        "2d",
        {
          alpha: false,
        }
      );

    if (!context) {
      return;
    }

    /*
     * Mirror inference frames to preserve the orientation
     * used by the earlier NINO collection/validation flow.
     */
    context.save();

    context.translate(
      width,
      0
    );

    context.scale(
      -1,
      1
    );

    context.drawImage(
      video,
      0,
      0,
      width,
      height
    );

    context.restore();


    waitingForInferenceRef.current =
      true;

    canvas.toBlob(
      async (
        blob
      ) => {
        if (!blob) {
          waitingForInferenceRef.current =
            false;

          return;
        }

        try {
          const buffer =
            await blob.arrayBuffer();

          if (
            socket.readyState
            ===
            WebSocket.OPEN
          ) {
            socket.send(
              buffer
            );
          } else {
            waitingForInferenceRef.current =
              false;
          }

        } catch {
          waitingForInferenceRef.current =
            false;
        }
      },

      "image/jpeg",

      0.62
    );
  }


  function startFrameLoop() {
    if (
      sendLoopRef.current
    ) {
      clearInterval(
        sendLoopRef.current
      );
    }

    /*
     * Maximum request rate ≈ 12 FPS.
     *
     * Backpressure makes the actual inference rate adapt
     * to the PC: no new frame is sent until the previous
     * prediction returns. This avoids a latency queue.
     */
    sendLoopRef.current =
      setInterval(
        sendFrame,
        83
      );
  }


  function connectWebSocket() {
    return new Promise(
      (
        resolve,
        reject
      ) => {
        const token =
          getToken();

        if (!token) {
          reject(
            new Error(
              "Please sign in again."
            )
          );

          return;
        }

        if (
          socketRef.current
          &&
          socketRef.current
            .readyState
          ===
          WebSocket.OPEN
        ) {
          resolve(
            socketRef.current
          );

          return;
        }

        closeWebSocket();

        const socket =
          new WebSocket(
            `${WS_BASE}/ws/live?token=${encodeURIComponent(
              token
            )}`
          );

        socket.binaryType =
          "arraybuffer";

        socket.onopen = () => {
          socketRef.current =
            socket;

          setSocketReady(true);

          startFrameLoop();

          resolve(socket);
        };


        socket.onmessage = (
          event
        ) => {
          waitingForInferenceRef.current =
            false;

          try {
            const data =
              JSON.parse(
                event.data
              );

            if (
              data.error
            ) {
              setNotice(
                data.error
              );

              return;
            }

            setLiveState(data);

            setLiveSeries(
              (
                current
              ) => {
                const next = [
                  ...current,

                  {
                    t:
                      new Date()
                        .toLocaleTimeString(
                          [],
                          {
                            hour12:
                              false,

                            minute:
                              "2-digit",

                            second:
                              "2-digit",
                          }
                        ),

                    ear:
                      Number(
                        data.ear
                        ||
                        0
                      ),

                    mar:
                      Number(
                        data.mar
                        ||
                        0
                      ),

                    confidence:
                      Number(
                        data
                          .head_direction_confidence
                        ||
                        0
                      )
                      *
                      100,
                  },
                ];

                return next.slice(
                  -35
                );
              }
            );

          } catch (error) {
            console.error(
              "WebSocket parse error:",
              error
            );
          }
        };


        socket.onerror = () => {
          waitingForInferenceRef.current =
            false;

          setSocketReady(false);

          reject(
            new Error(
              "Could not connect to NINO live inference."
            )
          );
        };


        socket.onclose = () => {
          waitingForInferenceRef.current =
            false;

          setSocketReady(false);

          if (
            socketRef.current
            ===
            socket
          ) {
            socketRef.current =
              null;
          }
        };
      }
    );
  }


  /* =====================================================
     DRIVE TIMER
  ===================================================== */

  function startDriveTimer() {
    setDriveSeconds(0);

    if (
      driveTimerRef.current
    ) {
      clearInterval(
        driveTimerRef.current
      );
    }

    const start =
      Date.now();

    driveTimerRef.current =
      setInterval(
        () => {
          setDriveSeconds(
            Math.floor(
              (
                Date.now()
                -
                start
              )
              /
              1000
            )
          );
        },
        500
      );
  }


  function stopDriveTimer() {
    if (
      driveTimerRef.current
    ) {
      clearInterval(
        driveTimerRef.current
      );

      driveTimerRef.current =
        null;
    }
  }


  function formatDuration(
    seconds
  ) {
    const minutes =
      Math.floor(
        seconds / 60
      );

    const remaining =
      seconds % 60;

    return (
      `${String(
        minutes
      ).padStart(
        2,
        "0"
      )}:${String(
        remaining
      ).padStart(
        2,
        "0"
      )}`
    );
  }


  /* =====================================================
     START DRIVE
  ===================================================== */

  async function startDrive() {
    setNotice(
      "Starting camera and AI inference..."
    );

    try {
      await startBrowserCamera();

      /*
       * Give React one render so the <video> exists.
       */
      await new Promise(
        (
          resolve
        ) =>
          setTimeout(
            resolve,
            50
          )
      );

      await attachStreamToVideo();

      await connectWebSocket();

      const data =
        await request(
          "/api/drive/start",
          {
            method: "POST",
          }
        );

      setLiveState({
        ...createEmptyLiveState(),
        connected: true,
        drive_active: true,
        session_id:
          data.session_id,
      });

      setLiveSeries([]);

      startDriveTimer();

      setNotice(
        `Drive active — session ${data.session_id}`
      );

      setPage(
        "live"
      );

    } catch (error) {
      setNotice(
        error.message
      );

      closeWebSocket();

      stopBrowserCamera();
    }
  }


  /* =====================================================
     END DRIVE
  ===================================================== */

  async function endDrive() {
    setNotice(
      "Ending drive and generating analytics..."
    );

    try {
      const data =
        await request(
          "/api/drive/end",
          {
            method: "POST",
          }
        );

      if (
        data.summary
      ) {
        setSummary(
          data.summary
        );
      }

      stopDriveTimer();

      closeWebSocket();

      stopBrowserCamera();

      setLiveState(
        createEmptyLiveState()
      );

      await loadSessions();

      if (
        !data.summary
      ) {
        await loadSummary();
      }

      setNotice(
        "Drive complete — analytics updated."
      );

      setPage(
        "analytics"
      );

    } catch (error) {
      setNotice(
        error.message
      );
    }
  }


  /* =====================================================
     EDITABLE PROFILE
  ===================================================== */

  useEffect(
    () => {
      if (
        page
        ===
        "settings"
      ) {
        setPage(
          "dashboard"
        );
      }
    },
    [
      page,
    ]
  );


  useEffect(
    () => {
      if (!user) {
        setProfileName("");
        setProfilePhone("");
        setProfileMessage("");
        return;
      }

      setProfileName(
        titleCaseName(
          user.name
          ||
          ""
        )
      );

      setProfilePhone(
        user.phone
        ||
        ""
      );

      setProfileMessage("");
    },
    [
      user?.name,
      user?.phone,
      user?.email,
    ]
  );


  async function saveProfile() {
    const cleanName =
      titleCaseName(
        profileName.trim()
      );

    const cleanPhone =
      profilePhone.trim();

    if (
      cleanName.length
      <
      2
    ) {
      setProfileMessage(
        "Enter your full name."
      );
      return;
    }

    setProfileSaving(true);
    setProfileMessage("");

    try {
      const {
        data,
        error,
      } =
        await supabase.auth
          .updateUser({
            data: {
              full_name:
                cleanName,

              phone:
                cleanPhone,

              role:
                user?.role
                ||
                "Driver",
            },
          });

      if (error) {
        throw error;
      }

      const {
        data:
          refreshed,
      } =
        await supabase.auth
          .refreshSession();

      if (
        refreshed
          ?.session
          ?.access_token
      ) {
        sessionStorage.setItem(
          "nino_token",
          refreshed
            .session
            .access_token
        );
      }

      setUser(
        (
          current
        ) => ({
          ...current,
          name:
            cleanName,
          phone:
            cleanPhone,
          role:
            current?.role
            ||
            data?.user
              ?.user_metadata
              ?.role
            ||
            "Driver",
        })
      );

      setProfileName(
        cleanName
      );

      setProfilePhone(
        cleanPhone
      );

      setProfileMessage(
        "Profile updated successfully."
      );

    } catch (error) {
      console.error(
        "Profile update:",
        error
      );

      setProfileMessage(
        error?.message
        ||
        "Could not update your profile."
      );

    } finally {
      setProfileSaving(false);
    }
  }


  function cancelProfileEdit() {
    setProfileName(
      titleCaseName(
        user?.name
        ||
        ""
      )
    );

    setProfilePhone(
      user?.phone
      ||
      ""
    );

    setProfileMessage("");
  }


  /* =====================================================
     LOGOUT
  ===================================================== */

  async function logout() {
    /*
     * Stop browser-owned realtime resources first.
     */
    stopDriveTimer();
    closeWebSocket();
    stopBrowserCamera();

    /*
     * Ask FastAPI to finish/save any active drive while
     * the Supabase access token is still available.
     */
    try {
      await request(
        "/api/auth/logout",
        {
          method: "POST",
        }
      );

    } catch (error) {
      console.error(
        "Backend logout cleanup:",
        error
      );
    }

    try {
      const {
        error,
      } = await supabase.auth
        .signOut();

      if (error) {
        throw error;
      }

    } catch (error) {
      console.error(
        "Supabase logout:",
        error
      );
    }

    sessionStorage.removeItem(
      "nino_token"
    );

    setUser(null);
    setProfileOpen(false);
    setNotice("");
    setLiveSeries([]);

    setLiveState(
      createEmptyLiveState()
    );
  }


  /* =====================================================
     INITIAL LOAD / AUTH URL / PAGE CLEANUP
  ===================================================== */

  useEffect(
    () => {
      const issue =
        parseAuthHashIssue();

      if (issue) {
        setAuthIssue(issue);
        setUser(null);

        sessionStorage.removeItem(
          "nino_token"
        );

        supabase.auth
          .signOut({
            scope: "local",
          })
          .catch(
            () => {}
          );

        window.history.replaceState(
          {},
          document.title,
          `${window.location.pathname}${window.location.search}`
        );

      } else {
        bootstrap();
      }


      const {
        data,
      } = supabase.auth
        .onAuthStateChange(
          (
            event,
            session
          ) => {
            if (
              session
              ?.access_token
            ) {
              sessionStorage.setItem(
                "nino_token",
                session.access_token
              );
            } else {
              sessionStorage.removeItem(
                "nino_token"
              );
            }

            if (
              event ===
              "PASSWORD_RECOVERY"
            ) {
              setAuthIssue(null);
              setPasswordRecovery(true);
              setUser(null);
            }

            if (
              event ===
              "SIGNED_OUT"
            ) {
              setUser(null);
            }
          }
        );

      return () => {
        data.subscription
          .unsubscribe();

        stopDriveTimer();
        closeWebSocket();
        stopBrowserCamera();
      };
    },
    []
  );


  useEffect(
    () => {
      if (!notice) {
        return undefined;
      }

      const timer =
        window.setTimeout(
          () =>
            setNotice(""),
          4000
        );

      return () =>
        window.clearTimeout(
          timer
        );
    },
    [notice]
  );


  useEffect(
    () => {
      const alertState =
        String(
          liveState
            .alert_state
          ||
          ""
        );

      const isCritical =
        Boolean(
          liveState
            .drive_active
        )
        &&
        alertState.startsWith(
          "CRITICAL_"
        );

      if (!isCritical) {
        lastCriticalAlertRef.current =
          "";
        return undefined;
      }

      if (
        lastCriticalAlertRef.current
        ===
        alertState
      ) {
        return undefined;
      }

      lastCriticalAlertRef.current =
        alertState;

      setAlertFlash(true);

      try {
        const AudioContextClass =
          window.AudioContext
          ||
          window.webkitAudioContext;

        if (AudioContextClass) {
          const context =
            new AudioContextClass();

          const oscillator =
            context.createOscillator();

          const gain =
            context.createGain();

          oscillator.type =
            "sine";

          oscillator.frequency.value =
            880;

          gain.gain.value =
            0.12;

          oscillator.connect(gain);
          gain.connect(
            context.destination
          );

          oscillator.start();

          oscillator.stop(
            context.currentTime
            +
            0.22
          );

          oscillator.onended =
            () =>
              context.close();
        }
      } catch {
        // Visual warning remains even if browser audio is blocked.
      }

      const timer =
        window.setTimeout(
          () =>
            setAlertFlash(false),
          650
        );

      return () =>
        window.clearTimeout(
          timer
        );
    },
    [
      liveState.drive_active,
      liveState.alert_state,
    ]
  );


  /* =====================================================
     CHART DATA
  ===================================================== */

  const directionData =
    useMemo(
      () =>
        [
          "FORWARD",
          "LEFT",
          "RIGHT",
          "UP",
          "DOWN",
        ].map(
          (
            name
          ) => ({
            name,

            value:
              Number(
                summary
                  ?.head_direction_percent
                  ?.[name]
                ||
                0
              ),
          })
        ),

      [
        summary,
      ]
    );


  const probabilityData =
    [
      "FORWARD",
      "LEFT",
      "RIGHT",
      "UP",
      "DOWN",
    ].map(
      (
        name
      ) => ({
        name,

        value:
          Number(
            liveState
              ?.head_direction_probabilities
              ?.[name]
            ||
            0
          )
          *
          100,
      })
    );


  const attentive =
    Number(
      summary
        ?.attentive_percent
      ||
      0
    );


  const attentionPie = [
    {
      name:
        "Attentive",

      value:
        attentive,
    },

    {
      name:
        "Other",

      value:
        Math.max(
          0,

          100
          -
          attentive
        ),
    },
  ];


  const weeklyTrend =
    useMemo(
      () => {
        const now =
          Date.now();

        const day =
          24
          *
          60
          *
          60
          *
          1000;

        const average = (
          rows
        ) => {
          if (
            rows.length
            ===
            0
          ) {
            return null;
          }

          return (
            rows.reduce(
              (
                total,
                row
              ) =>
                total
                +
                Number(
                  row
                    .attentive_percent
                  ||
                  0
                ),
              0
            )
            /
            rows.length
          );
        };

        const currentWeek =
          sessions.filter(
            (
              session
            ) => {
              const time =
                new Date(
                  session
                    .start_timestamp_utc
                  ||
                  0
                ).getTime();

              return (
                Number.isFinite(
                  time
                )
                &&
                now
                -
                time
                <=
                7
                *
                day
              );
            }
          );

        const previousWeek =
          sessions.filter(
            (
              session
            ) => {
              const time =
                new Date(
                  session
                    .start_timestamp_utc
                  ||
                  0
                ).getTime();

              const age =
                now
                -
                time;

              return (
                Number.isFinite(
                  time
                )
                &&
                age
                >
                7
                *
                day
                &&
                age
                <=
                14
                *
                day
              );
            }
          );

        const current =
          average(
            currentWeek
          );

        const previous =
          average(
            previousWeek
          );

        return {
          current,
          previous,
          change:
            current !== null
            &&
            previous !== null
              ? current
                -
                previous
              : null,
          driveCount:
            currentWeek.length,
        };
      },
      [
        sessions,
      ]
    );


  const visibleSessions =
    useMemo(
      () => {
        const query =
          historyQuery
            .trim()
            .toLowerCase();

        const filtered =
          sessions.filter(
            (
              session
            ) => {
              if (!query) {
                return true;
              }

              return (
                String(
                  session
                    .session_id
                  ||
                  ""
                )
                  .toLowerCase()
                  .includes(query)
                ||
                formatSessionDate(
                  session
                    .start_timestamp_utc
                )
                  .toLowerCase()
                  .includes(query)
              );
            }
          );

        return filtered.sort(
          (
            a,
            b
          ) => {
            if (
              historySort === "oldest"
            ) {
              return (
                new Date(
                  a.start_timestamp_utc
                  ||
                  0
                )
                -
                new Date(
                  b.start_timestamp_utc
                  ||
                  0
                )
              );
            }

            if (
              historySort === "attention"
            ) {
              return (
                Number(
                  b.attentive_percent
                  ||
                  0
                )
                -
                Number(
                  a.attentive_percent
                  ||
                  0
                )
              );
            }

            if (
              historySort === "alerts"
            ) {
              return (
                Number(
                  b.total_safety_alerts
                  ||
                  0
                )
                -
                Number(
                  a.total_safety_alerts
                  ||
                  0
                )
              );
            }

            return (
              new Date(
                b.start_timestamp_utc
                ||
                0
              )
              -
              new Date(
                a.start_timestamp_utc
                ||
                0
              )
            );
          }
        );
      },
      [
        sessions,
        historyQuery,
        historySort,
      ]
    );


  /* =====================================================
     LOGIN SCREEN
  ===================================================== */

  if (
    !user
    ||
    passwordRecovery
  ) {
    return (
      <Login
        onLogin={
          setUser
        }
        authIssue={
          authIssue
        }
        onClearAuthIssue={
          () =>
            setAuthIssue(
              null
            )
        }
        passwordRecovery={
          passwordRecovery
        }
        onRecoveryComplete={
          () =>
            setPasswordRecovery(
              false
            )
        }
      />
    );
  }


  /* =====================================================
     NAVIGATION
  ===================================================== */

  const navItems = [
    {
      id:
        "dashboard",

      label:
        "Dashboard",

      icon:
        <Gauge size={18} />,
    },

    {
      id:
        "live",

      label:
        "Live monitor",

      icon:
        <Video size={18} />,
    },

    {
      id:
        "analytics",

      label:
        "Analytics",

      icon:
        <BarChart3 size={18} />,
    },

    {
      id:
        "history",

      label:
        "Drive history",

      icon:
        <History size={18} />,
    },
  ];


  const driveActive =
    Boolean(
      liveState
        .drive_active
    );


  const currentEvents =
    liveState.events
    ||
    [];


  /* =====================================================
     APP UI
  ===================================================== */

  return (
    <div className="app-shell">

      {alertFlash && (
        <div
          aria-hidden="true"
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 9999,
            pointerEvents: "none",
            border: "12px solid rgba(220, 38, 38, 0.86)",
            boxShadow:
              "inset 0 0 90px rgba(220, 38, 38, 0.25)",
          }}
        />
      )}

      {/* Hidden canvas: only used to create AI JPEG frames */}
      <canvas
        ref={canvasRef}
        style={{
          display:
            "none",
        }}
      />


      {sidebarOpen && (
        <button
          className="scrim"

          onClick={
            () =>
              setSidebarOpen(
                false
              )
          }
        />
      )}


      {/* =================================================
          SIDEBAR
      ================================================== */}

      <aside
        className={
          sidebarOpen
            ? "sidebar open"
            : "sidebar"
        }
      >
        <div className="sidebar-header">

          <div className="logo-mark">
            N
          </div>

          <div>
            <strong>
              NINO
            </strong>

            <span>
              Driver Safety AI
            </span>
          </div>


          <button
            className="sidebar-close"

            onClick={
              () =>
                setSidebarOpen(
                  false
                )
            }
          >
            <X size={18} />
          </button>

        </div>


        <nav className="nav-list">

          <button
            className={
              page === "dashboard"
                ? "nav-link active"
                : "nav-link"
            }
            onClick={() => {
              setPage("dashboard");
              setSidebarOpen(false);
            }}
          >
            <Gauge size={18} />

            <span>
              Dashboard
            </span>
          </button>


          <button
            className={
              page === "live"
                ? "nav-link active"
                : "nav-link"
            }
            onClick={() => {
              setPage("live");
              setSidebarOpen(false);
            }}
          >
            <Video size={18} />

            <span>
              Live monitor
            </span>
          </button>


          <button
            className={
              page === "analytics"
                ? "nav-link active"
                : "nav-link"
            }
            onClick={() => {
              setPage("analytics");
              setSidebarOpen(false);
            }}
          >
            <BarChart3 size={18} />

            <span>
              Analytics
            </span>
          </button>


          <button
            className={
              page === "history"
                ? "nav-link active"
                : "nav-link"
            }
            onClick={() => {
              setPage("history");
              setSidebarOpen(false);
            }}
          >
            <History size={18} />

            <span>
              Drive history
            </span>
          </button>

        </nav>


        <div className="sidebar-footer">

          <div
            className={
              socketReady
                ? "system-status on"
                : "system-status"
            }
          >
            <span />

            {cameraReady
              ? "Camera: on"
              : "Camera: off"}
          </div>

          <small>
            {driveActive
              ? "Drive monitoring active"
              : "Start a drive when ready"}
          </small>

        </div>

      </aside>


      {/* =================================================
          MAIN SHELL
      ================================================== */}

      <div className="main-shell">

        <header className="topbar">

          <div className="topbar-left">

            <button
              className="icon-btn mobile-menu"

              onClick={
                () =>
                  setSidebarOpen(
                    true
                  )
              }
            >
              <Menu size={20} />
            </button>


            <div>
              <span className="page-kicker">
                NINO CONTROL CENTER
              </span>

              <h1>
                {
                  navItems.find(
                    (
                      item
                    ) =>
                      item.id
                      ===
                      page
                  )?.label
                  ||
                  (
                    page
                    ===
                    "profile"
                      ? "Profile"
                      :
                      "NINO"
                  )
                }
              </h1>
            </div>

          </div>


          <div className="topbar-actions">

            <div className="profile">

              <button
                className="profile-trigger"

                onClick={
                  () =>
                    setProfileOpen(
                      !profileOpen
                    )
                }
              >
                <div className="avatar">
                  {titleCaseName(
                    user.name
                  )
                    .charAt(0)
                    .toUpperCase()}
                </div>

                <div>
                  <strong>
                    {
                      titleCaseName(
                        user.name
                      )
                    }
                  </strong>

                  <span>
                    {
                      user.role
                    }
                  </span>
                </div>

                <ChevronDown
                  size={15}
                />
              </button>


              {profileOpen && (
                <div className="profile-menu">

                  <div className="profile-summary">
                    <CircleUserRound
                      size={32}
                    />

                    <div>
                      <strong>
                        {
                          titleCaseName(
                            user.name
                          )
                        }
                      </strong>

                      <span>
                        {
                          user.email
                        }
                      </span>
                    </div>
                  </div>


                  <button
                    onClick={() => {
                      setPage(
                        "profile"
                      );
                      setProfileOpen(
                        false
                      );
                    }}
                  >
                    <CircleUserRound
                      size={16}
                    />

                    Profile
                  </button>

                  <button
                    onClick={
                      logout
                    }
                  >
                    <LogOut
                      size={16}
                    />

                    Log out
                  </button>

                </div>
              )}

            </div>

          </div>

        </header>


        <main className="page">

          {notice && (
            <div className="notice">
              {
                notice
              }
            </div>
          )}


          {/* =================================================
              DASHBOARD
          ================================================== */}

          {page ===
            "dashboard"
            &&
            (
              <>
                <SectionTitle
                  eyebrow={
                    driveActive
                      ? "CURRENT DRIVE"
                      : "OVERVIEW"
                  }

                  title={
                    driveActive
                      ? `Drive in progress • ${formatDuration(
                          driveSeconds
                        )}`
                      : `Welcome back, ${titleCaseName(
                          user.name
                        ).split(
                          " "
                        )[0]}`
                  }

                  action={
                    driveActive
                      ? (
                        <button
                          className="btn danger"

                          onClick={
                            endDrive
                          }
                        >
                          <Square
                            size={16}
                          />

                          End drive
                        </button>
                      )
                      : (
                        <button
                          className="btn primary"

                          onClick={
                            startDrive
                          }
                        >
                          <Play
                            size={16}
                          />

                          Start drive
                        </button>
                      )
                  }
                />


                <section className="hero-grid">

                  <div className="camera-card panel">

                    <div className="panel-heading">

                      <div>
                        <span className="kicker">
                          {driveActive
                            ? "LIVE CAMERA"
                            : "DRIVER CAMERA"}
                        </span>

                        <h3>
                          {driveActive
                            ? "Real-time driver monitor"
                            : "Camera preview"}
                        </h3>
                      </div>


                      <span
                        className={
                          driveActive
                            ? "live-badge"
                            : "idle-badge"
                        }
                      >
                        {driveActive
                          ? "● LIVE"
                          : "IDLE"}
                      </span>

                    </div>


                    <div className="camera-frame">

                      {cameraReady ? (
                        <>
                          <video
                            ref={
                              videoRef
                            }

                            autoPlay

                            muted

                            playsInline

                            style={{
                              width:
                                "100%",

                              height:
                                "100%",

                              objectFit:
                                "cover",

                              transform:
                                "scaleX(-1)",

                              display:
                                "block",
                            }}
                          />


                          <LandmarkOverlay
                            overlay={
                              liveState
                                .landmark_overlay
                            }
                            faceDetected={
                              Boolean(
                                liveState
                                  .face_detected
                              )
                            }
                          />

                          <LivePerformanceHud
                            performance={
                              liveState
                                .performance
                            }
                            faceDetected={
                              Boolean(
                                liveState
                                  .face_detected
                              )
                            }
                          />

                          <CalibrationOverlay
                            calibration={
                              liveState?.calibration
                            }
                            calibrated={
                              Boolean(
                                liveState?.calibrated
                              )
                            }
                            driveActive={
                              Boolean(
                                driveActive
                              )
                            }
                          />


                          {driveActive && (
                            <div
                              style={{
                                position:
                                  "absolute",

                                left:
                                  "14px",

                                right:
                                  "14px",

                                bottom:
                                  "14px",

                                display:
                                  "flex",

                                justifyContent:
                                  "space-between",

                                gap:
                                  "10px",

                                pointerEvents:
                                  "none",
                              }}
                            >
                              <span className="recording-pill">
                                ● REC{" "}
                                {
                                  formatDuration(
                                    driveSeconds
                                  )
                                }
                              </span>

                              <span
                                className={
                                  String(
                                    liveState
                                      .alert_state
                                  ).includes(
                                    "ALERT"
                                  )
                                    ? "recording-pill"
                                    : "idle-pill"
                                }
                              >
                                {
                                  liveState
                                    .alert_state
                                  ||
                                  "NORMAL"
                                }
                              </span>
                            </div>
                          )}
                        </>
                      ) : (
                        <div className="camera-empty camera-empty-guide">
                          <div className="camera-guide-icon">
                            <Camera
                              size={32}
                            />
                          </div>

                          <strong>
                            Ready for your next drive
                          </strong>

                          <div className="camera-checklist">
                            <span>✓ Allow camera permission</span>
                            <span>✓ Sit upright and face the camera</span>
                            <span>✓ Use even lighting on your face</span>
                          </div>
                        </div>
                      )}

                    </div>

                  </div>


                  <div className="live-status panel">

                    <span className="kicker">
                      {driveActive
                        ? "LIVE DRIVER STATE"
                        : "MONITORING IDLE"}
                    </span>

                    <h3>
                      Safety status
                    </h3>


                    <div className="live-state-hero">

                      <div
                        className={
                          liveState.is_drowsy
                          ||
                          String(
                            liveState
                              .alert_state
                          ).includes(
                            "ALERT"
                          )
                            ? "status-orb alert"
                            : "status-orb"
                        }
                      >
                        <ShieldCheck
                          size={25}
                        />
                      </div>


                      <div>
                        <strong>
                          {driveActive
                            ? (
                                liveState
                                  .alert_state
                                ||
                                "NORMAL"
                              )
                            : "No active drive"}
                        </strong>

                        <span>
                          {driveActive
                            ? "Current safety state"
                            : "Start a drive to begin monitoring"}
                        </span>
                      </div>

                    </div>


                    <div className="compact-list">

                      <div>
                        <span>
                          Head direction
                        </span>

                        <strong>
                          {driveActive
                            ? (
                                liveState
                                  .head_direction
                                ||
                                "—"
                              )
                            : "—"}
                        </strong>
                      </div>


                      <div>
                        <span>
                          Detection confidence
                        </span>

                        <strong>
                          {driveActive
                            ? `${(
                                Number(
                                  liveState
                                    .head_direction_confidence
                                  ||
                                  0
                                )
                                *
                                100
                              ).toFixed(
                                0
                              )}%`
                            : "—"}
                        </strong>
                      </div>


                      <div>
                        <span>
                          Eye state
                        </span>

                        <strong>
                          {driveActive
                            ? (
                                liveState
                                  .eye_state
                                ||
                                "—"
                              )
                            : "—"}
                        </strong>
                      </div>


                      <div>
                        <span>
                          Distraction
                        </span>

                        <strong>
                          {driveActive
                            ? (
                                liveState
                                  .distraction_state
                                ||
                                "—"
                              )
                            : "—"}
                        </strong>
                      </div>

                    </div>

                  </div>

                </section>


                {!driveActive && (
                  <>
                    <section className="stat-grid">

                      <StatCard
                        icon={
                          <ShieldCheck />
                        }

                        label="Safe / attentive"

                        value={
                          `${Number(
                            summary
                              ?.attentive_percent
                            ||
                            0
                          ).toFixed(
                            1
                          )}%`
                        }

                        helper="Latest completed drive"
                      />


                      <StatCard
                        icon={
                          <Activity />
                        }

                        label="Head orientation away (diagnostic)"

                        value={
                          `${Number(
                            summary
                              ?.head_away_percent
                            ||
                            0
                          ).toFixed(
                            1
                          )}%`
                        }

                        helper="Overlaps with attentive time; not a 100% split"
                      />


                      <StatCard
                        icon={
                          <Gauge />
                        }

                        label="Confirmed unsafe distraction"

                        value={
                          `${Number(
                            summary
                              ?.confirmed_distraction_percent
                            ||
                            0
                          ).toFixed(
                            1
                          )}%`
                        }

                        helper="Sustained temporal state"

                        tone={
                          Number(
                            summary
                              ?.confirmed_distraction_percent
                            ||
                            0
                          )
                          >
                          0
                            ? "danger"
                            : "neutral"
                        }
                      />


                      <StatCard
                        icon={
                          <BellRing />
                        }

                        label="Drowsiness events"

                        value={
                          summary
                            ?.drowsiness_event_count
                          ??
                          0
                        }

                        helper="Latest completed drive"
                      />

                    </section>

                    <section className="panel weekly-trend-card">
                      <div>
                        <span className="kicker">
                          WEEKLY ATTENTION
                        </span>

                        <h3>
                          Your recent trend
                        </h3>

                        <p>
                          {weeklyTrend.current === null
                            ? "Complete a few drives to build your weekly trend."
                            : `${weeklyTrend.current.toFixed(1)}% average attentive time across ${weeklyTrend.driveCount} drive${weeklyTrend.driveCount === 1 ? "" : "s"} this week.`}
                        </p>
                      </div>

                      <div className="weekly-trend-score">
                        <strong>
                          {weeklyTrend.change === null
                            ? "—"
                            : `${weeklyTrend.change >= 0 ? "+" : ""}${weeklyTrend.change.toFixed(1)}%`}
                        </strong>

                        <span>
                          {weeklyTrend.change === null
                            ? "Need previous-week data"
                            : "vs previous 7 days"}
                        </span>
                      </div>
                    </section>


                    <section className="dashboard-grid">

                      <div className="panel chart-panel">

                        <div className="panel-heading">

                          <div>
                            <span className="kicker">
                              DATA SCIENCE
                            </span>

                            <h3>
                              Head direction distribution
                            </h3>
                          </div>

                        </div>


                        <ResponsiveContainer
                          width="100%"
                          height={280}
                        >
                          <BarChart
                            data={
                              directionData
                            }
                          >
                            <CartesianGrid
                              strokeDasharray="3 3"
                              vertical={
                                false
                              }
                            />

                            <XAxis
                              dataKey="name"
                              tickLine={
                                false
                              }
                              axisLine={
                                false
                              }
                            />

                            <YAxis
                              domain={[
                                0,
                                100,
                              ]}
                              tickLine={
                                false
                              }
                              axisLine={
                                false
                              }
                              tickFormatter={
                                (
                                  value
                                ) =>
                                  `${value}%`
                              }
                            />

                            <Tooltip
                              formatter={
                                (
                                  value
                                ) =>
                                  `${Number(
                                    value
                                  ).toFixed(
                                    1
                                  )}%`
                              }
                            />

                            <Bar
                              dataKey="value"
                              radius={[
                                8,
                                8,
                                0,
                                0,
                              ]}
                              fill="#1f8f63"
                            />
                          </BarChart>
                        </ResponsiveContainer>

                      </div>


                      <div className="panel chart-panel">

                        <div className="panel-heading">

                          <div>
                            <span className="kicker">
                              DRIVER ATTENTION
                            </span>

                            <h3>
                              Session quality
                            </h3>
                          </div>

                        </div>


                        <div className="donut-wrap">

                          <ResponsiveContainer
                            width="100%"
                            height={230}
                          >
                            <PieChart>
                              <Pie
                                data={
                                  attentionPie
                                }

                                dataKey="value"

                                innerRadius={72}

                                outerRadius={98}

                                startAngle={90}

                                endAngle={-270}
                              >
                                <Cell
                                  fill="#1f8f63"
                                />

                                <Cell
                                  fill="#e6ece9"
                                />
                              </Pie>
                            </PieChart>
                          </ResponsiveContainer>


                          <div className="donut-label">

                            <strong>
                              {
                                attentive.toFixed(
                                  1
                                )
                              }
                              %
                            </strong>

                            <span>
                              attentive
                            </span>

                          </div>

                        </div>

                      </div>

                    </section>
                  </>
                )}


                {driveActive && (
                  <section className="panel">

                    <div className="panel-heading">

                      <div>
                        <span className="kicker">
                          LIVE EVENT TIMELINE
                        </span>

                        <h3>
                          Current drive events
                        </h3>
                      </div>

                    </div>


                    <div className="compact-list roomy">

                      {currentEvents.length
                        ===
                        0
                        ? (
                          <div>
                            <span>
                              Waiting for events…
                            </span>

                            <strong>
                              —
                            </strong>
                          </div>
                        )
                        :
                        [...currentEvents]
                          .reverse()
                          .slice(
                            0,
                            8
                          )
                          .map(
                            (
                              event,
                              index
                            ) => (
                              <div
                                key={
                                  `${event.elapsed_seconds}-${event.type}-${index}`
                                }
                              >
                                <span>
                                  {Number(
                                    event
                                      .elapsed_seconds
                                    ||
                                    0
                                  ).toFixed(
                                    1
                                  )}
                                  s
                                  {" • "}
                                  {
                                    event
                                      .type
                                  }
                                </span>

                                <strong>
                                  {
                                    event
                                      .message
                                  }
                                </strong>
                              </div>
                            )
                          )}

                    </div>

                  </section>
                )}

              </>
            )}


          {/* =================================================
              LIVE MONITOR
          ================================================== */}

          {page ===
            "live"
            &&
            (
              <>
                <SectionTitle
                  eyebrow="REAL-TIME COMPUTER VISION"

                  title={
                    driveActive
                      ? `Live driver monitoring • ${formatDuration(
                          driveSeconds
                        )}`
                      : "Live driver monitoring"
                  }

                  action={
                    driveActive
                      ? (
                        <button
                          className="btn danger"

                          onClick={
                            endDrive
                          }
                        >
                          <Square
                            size={16}
                          />

                          End drive
                        </button>
                      )
                      : (
                        <button
                          className="btn primary"

                          onClick={
                            startDrive
                          }
                        >
                          <Play
                            size={16}
                          />

                          Start drive
                        </button>
                      )
                  }
                />


                <section className="live-grid">

                  <div className="panel camera-live-panel">

                    <div className="camera-frame large">

                      {cameraReady ? (
                        <>
                        <video
                          ref={
                            videoRef
                          }

                          autoPlay

                          muted

                          playsInline

                          style={{
                            width:
                              "100%",

                            height:
                              "100%",

                            objectFit:
                              "cover",

                            transform:
                              "scaleX(-1)",

                            display:
                              "block",
                          }}
                        />


                        <LandmarkOverlay
                          overlay={
                            liveState
                              .landmark_overlay
                          }
                          faceDetected={
                            Boolean(
                              liveState
                                .face_detected
                            )
                          }
                        />

                        <LivePerformanceHud
                          performance={
                            liveState
                              .performance
                          }
                          faceDetected={
                            Boolean(
                              liveState
                                .face_detected
                            )
                          }
                        />


                        <HeadDirectionArrow
                          direction={
                            liveState
                              .head_direction
                          }
                          visible={
                            Boolean(
                              liveState
                                .face_detected
                            )
                          }
                        />

                        <CalibrationOverlay
                          calibration={
                            liveState?.calibration
                          }
                          calibrated={
                            Boolean(
                              liveState?.calibrated
                            )
                          }
                          driveActive={
                            Boolean(
                              driveActive
                            )
                          }
                        />
                        </>
                      ) : (
                        <div className="camera-empty">
                          <Camera
                            size={42}
                          />

                          <strong>
                            Camera is off
                          </strong>

                          <span>
                            Start a drive to
                            activate the real-time
                            browser camera.
                          </span>
                        </div>
                      )}

                    </div>


                    <div className="camera-actions">

                      <span
                        className={
                          driveActive
                            ? "recording-pill"
                            : "idle-pill"
                        }
                      >
                        {driveActive
                          ? `● Recording ${formatDuration(
                              driveSeconds
                            )}`
                          : "Not recording"}
                      </span>


                      <span
                        className={
                          socketReady
                            ? "recording-pill"
                            : "idle-pill"
                        }
                      >
                        {socketReady
                          ? "AI connected"
                          : "AI disconnected"}
                      </span>

                    </div>

                  </div>


                  <div className="panel live-metrics">

                    <span className="kicker">
                      LIVE FEATURES
                    </span>

                    <h3>
                      Driver state vector
                    </h3>


                    <div className="feature-grid">

                      <div>
                        <span>
                          EAR
                        </span>

                        <strong>
                          {Number(
                            liveState
                              .ear
                            ||
                            0
                          ).toFixed(
                            3
                          )}
                        </strong>
                      </div>


                      <div>
                        <span>
                          MAR
                        </span>

                        <strong>
                          {Number(
                            liveState
                              .mar
                            ||
                            0
                          ).toFixed(
                            3
                          )}
                        </strong>
                      </div>


                      <div>
                        <span>
                          Head direction
                        </span>

                        <strong>
                          {
                            liveState
                              .head_direction
                            ||
                            "—"
                          }
                        </strong>
                      </div>


                      <div>
                        <span>
                          Detection confidence
                        </span>

                        <strong>
                          {(
                            Number(
                              liveState
                                .head_direction_confidence
                              ||
                              0
                            )
                            *
                            100
                          ).toFixed(
                            0
                          )}
                          %
                        </strong>
                      </div>


                      <div>
                        <span>
                          Eye state
                        </span>

                        <strong
                          className={`state-chip ${
                            String(
                              liveState
                                .eye_state
                              ||
                              ""
                            ).toUpperCase()
                            ===
                            "OPEN"
                              ? "good"
                              :
                            String(
                              liveState
                                .eye_state
                              ||
                              ""
                            ).toUpperCase()
                            ===
                            "CLOSED"
                              ? "danger"
                              : "neutral"
                          }`}
                        >
                          {
                            liveState
                              .eye_state
                            ||
                            "—"
                          }
                        </strong>
                      </div>


                      <div>
                        <span>
                          Alert state
                        </span>

                        <strong
                          className={`state-chip ${
                            String(
                              liveState
                                .alert_state
                              ||
                              ""
                            ).includes(
                              "CRITICAL"
                            )
                              ? "danger"
                              :
                            String(
                              liveState
                                .alert_state
                              ||
                              ""
                            ).includes(
                              "WARNING"
                            )
                              ? "warning"
                              : "good"
                          }`}
                        >
                          {
                            liveState
                              .alert_state
                            ||
                            "NORMAL"
                          }
                        </strong>
                      </div>


                      <div>
                        <span>
                          Away duration
                        </span>

                        <strong>
                          {Number(
                            liveState
                              .distraction_duration
                            ||
                            0
                          ).toFixed(
                            2
                          )}
                          {" "}s
                        </strong>
                      </div>


                      <div>
                        <span>
                          Face
                        </span>

                        <strong
                          className={`state-chip ${
                            liveState
                              .face_detected
                              ? "good"
                              : "warning"
                          }`}
                        >
                          {liveState
                            .face_detected
                            ? "DETECTED"
                            : "NOT DETECTED"}
                        </strong>
                      </div>


                      <div>
                        <span>
                          AI FPS
                        </span>

                        <strong>
                          {Number(
                            liveState
                              .performance
                              ?.ai_fps
                            ||
                            0
                          ).toFixed(
                            1
                          )}
                        </strong>
                      </div>


                      <div>
                        <span>
                          Inference latency
                        </span>

                        <strong>
                          {Number(
                            liveState
                              .performance
                              ?.inference_ms
                            ||
                            0
                          ).toFixed(
                            0
                          )}
                          {" "}ms
                        </strong>
                      </div>

                    </div>

                  </div>

                </section>


                <section className="dashboard-grid">

                  <div className="panel chart-panel">

                    <div className="panel-heading">

                      <div>
                        <span className="kicker">
                          LIVE SIGNALS
                        </span>

                        <h3>
                          Eye closure signal (EAR)
                        </h3>

                        <small className="chart-note">
                          Lower EAR means the eyes are more closed.
                        </small>
                      </div>

                    </div>


                    <ResponsiveContainer
                      width="100%"
                      height={270}
                    >
                      <LineChart
                        data={
                          liveSeries
                        }
                      >
                        <CartesianGrid
                          strokeDasharray="3 3"
                          vertical={
                            false
                          }
                        />

                        <XAxis
                          dataKey="t"
                          hide
                        />

                        <YAxis
                          tickLine={
                            false
                          }
                          axisLine={
                            false
                          }
                        />

                        <Tooltip />

                        <ReferenceLine
                          y={0.20}
                          stroke="#c13b3b"
                          strokeDasharray="5 4"
                          label={{
                            value: "closure threshold",
                            position: "insideTopRight",
                            fill: "#9a4a4a",
                            fontSize: 10,
                          }}
                        />

                        <Line
                          type="monotone"

                          dataKey="ear"

                          name="EAR"

                          stroke="#1f8f63"

                          strokeWidth={2}

                          dot={
                            false
                          }
                        />

                        <Line
                          type="monotone"

                          dataKey="mar"

                          name="MAR"

                          stroke="#3456d1"

                          strokeWidth={2}

                          dot={
                            false
                          }
                        />
                      </LineChart>
                    </ResponsiveContainer>

                  </div>


                  <div className="panel chart-panel">

                    <div className="panel-heading">

                      <div>
                        <span className="kicker">
                          RANDOM FOREST
                        </span>

                        <h3>
                          Live class probabilities
                        </h3>
                      </div>

                    </div>


                    <ResponsiveContainer
                      width="100%"
                      height={270}
                    >
                      <BarChart
                        data={
                          probabilityData
                        }

                        layout="vertical"
                      >
                        <CartesianGrid
                          strokeDasharray="3 3"

                          horizontal={
                            false
                          }
                        />

                        <XAxis
                          type="number"

                          domain={[
                            0,
                            100,
                          ]}

                          hide
                        />

                        <YAxis
                          type="category"

                          dataKey="name"

                          tickLine={
                            false
                          }

                          axisLine={
                            false
                          }

                          width={70}
                        />

                        <Tooltip
                          formatter={
                            (
                              value
                            ) =>
                              `${Number(
                                value
                              ).toFixed(
                                1
                              )}%`
                          }
                        />

                        <Bar
                          dataKey="value"

                          fill="#3456d1"

                          radius={[
                            0,
                            7,
                            7,
                            0,
                          ]}
                        />
                      </BarChart>
                    </ResponsiveContainer>

                  </div>

                </section>


                <section className="panel">

                  <div className="panel-heading">

                    <div>
                      <span className="kicker">
                        EVENT TIMELINE
                      </span>

                      <h3>
                        Real-time safety events
                      </h3>
                    </div>

                  </div>


                  <div className="compact-list roomy">

                    {currentEvents.length
                      ===
                      0
                      ? (
                        <div>
                          <span>
                            No safety events yet
                          </span>

                          <strong>
                            —
                          </strong>
                        </div>
                      )
                      :
                      [...currentEvents]
                        .reverse()
                        .slice(
                          0,
                          12
                        )
                        .map(
                          (
                            event,
                            index
                          ) => (
                            <div
                              key={
                                `${event.elapsed_seconds}-${event.type}-${index}`
                              }
                            >
                              <span>
                                {Number(
                                  event
                                    .elapsed_seconds
                                  ||
                                  0
                                ).toFixed(
                                  1
                                )}
                                s
                                {" • "}
                                {
                                  event
                                    .type
                                }
                              </span>

                              <strong>
                                {
                                  event
                                    .message
                                }
                              </strong>
                            </div>
                          )
                        )}

                  </div>

                </section>

              </>
            )}


          {/* =================================================
              ANALYTICS
          ================================================== */}

          {page ===
            "analytics"
            &&
            (
              <>
                <SectionTitle
                  eyebrow="LATEST COMPLETED DRIVE"

                  title="Drive intelligence"

                  action={
                    <button
                      className="btn secondary"

                      onClick={
                        loadSummary
                      }
                    >
                      <RefreshCcw
                        size={15}
                      />

                      Refresh
                    </button>
                  }
                />


                <section className="stat-grid">

                  <StatCard
                    icon={
                      <Activity />
                    }

                    label="Duration"

                    value={
                      formatDriveDuration(
                        summary
                          ?.drive_duration_seconds
                      )
                    }
                  />


                  <StatCard
                    icon={
                      <ShieldCheck />
                    }

                    label="Safe / attentive"

                    value={
                      `${attentive.toFixed(
                        1
                      )}%`
                    }

                    helper="Excludes sustained distraction and drowsiness"
                  />


                  <StatCard
                    icon={
                      <Gauge />
                    }

                    label="Head orientation away (diagnostic)"

                    value={
                      `${Number(
                        summary
                          ?.head_away_percent
                        ||
                        0
                      ).toFixed(
                        1
                      )}%`
                    }

                    helper="Includes brief normal glances"
                  />


                  <StatCard
                    icon={
                      <BellRing />
                    }

                    label="Safety alerts"

                    value={
                      summary
                        ?.total_safety_alerts
                      ??
                      0
                    }
                  />

                </section>


                <section className="dashboard-grid">

                  <div className="panel chart-panel">

                    <div className="panel-heading">

                      <div>
                        <span className="kicker">
                          BEHAVIOUR PROFILE
                        </span>

                        <h3>
                          Head direction distribution
                        </h3>
                      </div>

                    </div>


                    <ResponsiveContainer
                      width="100%"
                      height={310}
                    >
                      <BarChart
                        data={
                          directionData
                        }
                      >
                        <CartesianGrid
                          strokeDasharray="3 3"
                          vertical={
                            false
                          }
                        />

                        <XAxis
                          dataKey="name"

                          axisLine={
                            false
                          }

                          tickLine={
                            false
                          }
                        />

                        <YAxis
                          domain={[
                            0,
                            100,
                          ]}

                          axisLine={
                            false
                          }

                          tickLine={
                            false
                          }
                        />

                        <Tooltip />

                        <Bar
                          dataKey="value"

                          fill="#1f8f63"

                          radius={[
                            8,
                            8,
                            0,
                            0,
                          ]}
                        />
                      </BarChart>
                    </ResponsiveContainer>

                  </div>


                  <div className="panel">

                    <span className="kicker">
                      SAFETY EVENTS
                    </span>

                    <h3>
                      Event summary
                    </h3>


                    <div className="compact-list roomy">

                      <div>
                        <span>
                          Blinks
                        </span>

                        <strong>
                          {
                            summary
                              ?.blink_count
                            ??
                            0
                          }
                        </strong>
                      </div>


                      <div>
                        <span>
                          Long eye closures
                        </span>

                        <strong>
                          {
                            summary
                              ?.long_eye_closure_count
                            ??
                            0
                          }
                        </strong>
                      </div>


                      <div>
                        <span>
                          Drowsiness events
                        </span>

                        <strong>
                          {
                            summary
                              ?.drowsiness_event_count
                            ??
                            0
                          }
                        </strong>
                      </div>


                      <div>
                        <span>
                          Possible yawns
                        </span>

                        <strong>
                          {
                            summary
                              ?.yawn_count
                            ??
                            0
                          }
                        </strong>
                      </div>


                      <div>
                        <span>
                          Distraction events
                        </span>

                        <strong>
                          {
                            summary
                              ?.distraction_event_count
                            ??
                            0
                          }
                        </strong>
                      </div>


                      <div>
                        <span>
                          Confirmed unsafe distraction
                        </span>

                        <strong>
                          {Number(
                            summary
                              ?.confirmed_distraction_percent
                            ||
                            0
                          ).toFixed(
                            1
                          )}
                          %
                        </strong>
                      </div>

                    </div>

                  </div>

                </section>

              </>
            )}


          {/* =================================================
              PROFILE
          ================================================== */}

          {page ===
            "profile"
            &&
            (
              <>
                <SectionTitle
                  eyebrow="ACCOUNT"
                  title="Profile"
                />

                <section
                  className="panel"
                  style={{
                    display:
                      "grid",
                    gridTemplateColumns:
                      "220px minmax(0, 1fr)",
                    gap:
                      "34px",
                    alignItems:
                      "start",
                  }}
                >
                  <div
                    style={{
                      display:
                        "grid",
                      justifyItems:
                        "center",
                      gap:
                        "12px",
                      padding:
                        "18px 8px 8px",
                      borderRight:
                        "1px solid #e7ece9",
                    }}
                  >
                    <div
                      className="avatar"
                      style={{
                        width:
                          "132px",
                        height:
                          "132px",
                        fontSize:
                          "48px",
                      }}
                    >
                      {titleCaseName(
                        profileName
                        ||
                        user.name
                      )
                        .charAt(0)
                        .toUpperCase()}
                    </div>

                    <div
                      style={{
                        textAlign:
                          "center",
                      }}
                    >
                      <strong
                        style={{
                          display:
                            "block",
                          fontSize:
                            "14px",
                        }}
                      >
                        Driver profile
                      </strong>

                      <small
                        style={{
                          display:
                            "block",
                          marginTop:
                            "4px",
                          color:
                            "#7a8984",
                          lineHeight:
                            1.5,
                        }}
                      >
                        Your profile details are saved
                        securely with your account.
                      </small>
                    </div>
                  </div>


                  <div
                    style={{
                      display:
                        "grid",
                      gap:
                        "18px",
                    }}
                  >
                    <div
                      style={{
                        display:
                          "grid",
                        gridTemplateColumns:
                          "repeat(2, minmax(0, 1fr))",
                        gap:
                          "16px",
                      }}
                    >
                      <label
                        style={{
                          display:
                            "grid",
                          gap:
                            "7px",
                          fontSize:
                            "12px",
                          fontWeight:
                            700,
                          color:
                            "#28362f",
                        }}
                      >
                        Full name

                        <input
                          value={
                            profileName
                          }
                          onChange={
                            (
                              event
                            ) => {
                              setProfileName(
                                event
                                  .target
                                  .value
                              );

                              setProfileMessage(
                                ""
                              );
                            }
                          }
                          placeholder="Your full name"
                          autoComplete="name"
                        />
                      </label>


                      <label
                        style={{
                          display:
                            "grid",
                          gap:
                            "7px",
                          fontSize:
                            "12px",
                          fontWeight:
                            700,
                          color:
                            "#28362f",
                        }}
                      >
                        Email address

                        <input
                          value={
                            user.email
                            ||
                            ""
                          }
                          readOnly
                          aria-readonly="true"
                          style={{
                            background:
                              "#f4f6f5",
                            color:
                              "#7a8984",
                            cursor:
                              "not-allowed",
                          }}
                        />
                      </label>


                      <label
                        style={{
                          display:
                            "grid",
                          gap:
                            "7px",
                          fontSize:
                            "12px",
                          fontWeight:
                            700,
                          color:
                            "#28362f",
                        }}
                      >
                        Phone
                        <span
                          style={{
                            color:
                              "#8a9893",
                            fontWeight:
                              500,
                          }}
                        >
                          Optional
                        </span>

                        <input
                          value={
                            profilePhone
                          }
                          onChange={
                            (
                              event
                            ) => {
                              setProfilePhone(
                                event
                                  .target
                                  .value
                              );

                              setProfileMessage(
                                ""
                              );
                            }
                          }
                          placeholder="+91 98765 43210"
                          autoComplete="tel"
                        />
                      </label>


                      <label
                        style={{
                          display:
                            "grid",
                          gap:
                            "7px",
                          fontSize:
                            "12px",
                          fontWeight:
                            700,
                          color:
                            "#28362f",
                        }}
                      >
                        Role

                        <input
                          value={
                            user.role
                            ||
                            "Driver"
                          }
                          readOnly
                          aria-readonly="true"
                          style={{
                            background:
                              "#f4f6f5",
                            color:
                              "#53635d",
                            cursor:
                              "not-allowed",
                          }}
                        />
                      </label>
                    </div>


                    <div
                      style={{
                        display:
                          "flex",
                        alignItems:
                          "center",
                        gap:
                          "10px",
                        flexWrap:
                          "wrap",
                      }}
                    >
                      <button
                        className="btn primary"
                        onClick={
                          saveProfile
                        }
                        disabled={
                          profileSaving
                        }
                      >
                        {profileSaving
                          ? "Saving..."
                          : "Save changes"}
                      </button>

                      <button
                        className="btn secondary"
                        onClick={
                          cancelProfileEdit
                        }
                        disabled={
                          profileSaving
                        }
                      >
                        Cancel
                      </button>

                      {profileMessage && (
                        <span
                          role="status"
                          style={{
                            color:
                              profileMessage
                                .toLowerCase()
                                .includes(
                                  "success"
                                )
                                ? "#147652"
                                : "#a33a3a",
                            fontSize:
                              "12px",
                            fontWeight:
                              600,
                          }}
                        >
                          {profileMessage}
                        </span>
                      )}
                    </div>

                    <p
                      style={{
                        margin: 0,
                        color:
                          "#788882",
                        fontSize:
                          "11px",
                        lineHeight:
                          1.55,
                      }}
                    >
                      Email and role are protected account fields.
                      Your editable name and phone number are stored
                      in your authenticated Supabase profile metadata.
                    </p>
                  </div>
                </section>
              </>
            )}


          {/* =================================================
              HISTORY
          ================================================== */}

          {page ===
            "history"
            &&
            (
              <>
                <SectionTitle
                  eyebrow="SESSION HISTORY"
                  title="Previous drives"
                  action={
                    <button
                      className="btn secondary"
                      onClick={
                        loadSessions
                      }
                    >
                      <RefreshCcw
                        size={15}
                      />
                      Refresh
                    </button>
                  }
                />


                <section
                  className="panel"
                  style={{
                    display: "grid",
                    gridTemplateColumns:
                      "minmax(0, 1fr) 180px",
                    gap: "10px",
                    marginBottom: "14px",
                  }}
                >
                  <input
                    value={historyQuery}
                    onChange={
                      (event) =>
                        setHistoryQuery(
                          event.target.value
                        )
                    }
                    placeholder="Search by date or session ID"
                    aria-label="Search drive history"
                  />

                  <select
                    value={historySort}
                    onChange={
                      (event) =>
                        setHistorySort(
                          event.target.value
                        )
                    }
                    aria-label="Sort drive history"
                  >
                    <option value="newest">
                      Newest first
                    </option>

                    <option value="oldest">
                      Oldest first
                    </option>

                    <option value="attention">
                      Highest attention
                    </option>

                    <option value="alerts">
                      Most alerts
                    </option>
                  </select>
                </section>


                <section className="panel table-panel">

                  <div className="table-head">
                    <span>
                      Drive
                    </span>

                    <span>
                      Duration
                    </span>

                    <span>
                      Attentive
                    </span>

                    <span>
                      Distractions
                    </span>

                    <span>
                      Alerts
                    </span>
                  </div>


                  {visibleSessions.length
                    ===
                    0
                    ? (
                      <div className="empty-state">
                        No matching drive sessions.
                      </div>
                    )
                    :
                    visibleSessions.map(
                      (
                        session
                      ) => {
                        const attentiveValue =
                          Number(
                            session
                              .attentive_percent
                            ||
                            0
                          );

                        const alertValue =
                          Number(
                            session
                              .total_safety_alerts
                            ||
                            0
                          );

                        const attentionColor =
                          attentiveValue >= 85
                            ? "#1f8f63"
                            : attentiveValue >= 65
                            ? "#b77a00"
                            : "#c13b3b";

                        const alertColor =
                          alertValue === 0
                            ? "#1f8f63"
                            : alertValue <= 2
                            ? "#b77a00"
                            : "#c13b3b";

                        return (
                          <button
                            type="button"
                            className="table-row"
                            key={
                              session
                                .session_id
                            }
                            onClick={
                              () =>
                                openSession(
                                  session
                                    .session_id
                                )
                            }
                            style={{
                              width: "100%",
                              border: 0,
                              background:
                                "transparent",
                              textAlign:
                                "left",
                              cursor:
                                "pointer",
                              alignItems:
                                "center",
                            }}
                          >
                            <span
                              style={{
                                display:
                                  "grid",
                                gap: "3px",
                              }}
                            >
                              <strong>
                                {
                                  formatSessionDate(
                                    session
                                      .start_timestamp_utc
                                  )
                                }
                              </strong>

                              <small
                                style={{
                                  opacity:
                                    0.62,
                                }}
                              >
                                ID{" "}
                                {
                                  String(
                                    session
                                      .session_id
                                    ||
                                    ""
                                  )
                                    .slice(
                                      0,
                                      12
                                    )
                                }
                              </small>
                            </span>

                            <span>
                              {
                                formatDriveDuration(
                                  session
                                    .drive_duration_seconds
                                )
                              }
                            </span>

                            <span>
                              <strong
                                style={{
                                  color:
                                    attentionColor,
                                }}
                              >
                                {
                                  attentiveValue
                                    .toFixed(
                                      1
                                    )
                                }
                                %
                              </strong>
                            </span>

                            <span>
                              {
                                session
                                  .distraction_event_count
                                ??
                                0
                              }
                            </span>

                            <span
                              style={{
                                display:
                                  "flex",
                                alignItems:
                                  "center",
                                justifyContent:
                                  "space-between",
                                gap: "8px",
                              }}
                            >
                              <strong
                                style={{
                                  color:
                                    alertColor,
                                }}
                              >
                                {
                                  alertValue
                                }
                              </strong>

                              <ChevronRight
                                size={16}
                              />
                            </span>
                          </button>
                        );
                      }
                    )}

                </section>


                {sessionLoading && (
                  <section
                    className="panel"
                    style={{
                      marginTop: "14px",
                      minHeight: "160px",
                      display: "grid",
                      placeItems: "center",
                    }}
                  >
                    <div
                      style={{
                        display: "grid",
                        justifyItems: "center",
                        gap: "10px",
                        color: "#6e7e78",
                      }}
                    >
                      <RefreshCcw
                        size={22}
                        className="spin"
                      />
                      <span>
                        Loading drive intelligence…
                      </span>
                    </div>
                  </section>
                )}


                {sessionDetail && (() => {
                  const detailSummary =
                    sessionDetail.summary || {};

                  const detailInsights =
                    sessionDetail.insights || {};

                  const scoreInfo =
                    detailInsights.driver_safety_score || {};

                  const detailEvents =
                    Array.isArray(sessionDetail.events)
                      ? sessionDetail.events
                      : [];

                  const detailSamples =
                    Array.isArray(sessionDetail.samples)
                      ? sessionDetail.samples
                      : [];

                  const attentionSeries =
                    buildAttentionSeries(
                      detailSamples
                    );

                  const safetyScore =
                    Number(
                      scoreInfo.score || 0
                    );

                  const scoreColor =
                    safetyScore >= 90
                      ? "#1f8f63"
                      : safetyScore >= 75
                      ? "#b77a00"
                      : "#c13b3b";

                  return (
                    <section
                      style={{
                        display: "grid",
                        gap: "14px",
                        marginTop: "14px",
                      }}
                    >
                      <section className="panel">
                        <div className="panel-heading">
                          <div>
                            <span className="kicker">
                              SESSION DETAIL
                            </span>

                            <h3>
                              {
                                formatSessionDate(
                                  detailSummary
                                    .start_timestamp_utc
                                )
                              }
                            </h3>

                            <small
                              style={{
                                color: "#7b8a84",
                              }}
                            >
                              ID{" "}
                              {
                                String(
                                  detailSummary
                                    .session_id
                                  ||
                                  ""
                                ).slice(
                                  0,
                                  12
                                )
                              }
                            </small>
                          </div>

                          <button
                            className="icon-btn"
                            onClick={
                              () =>
                                setSessionDetail(
                                  null
                                )
                            }
                            aria-label="Close session detail"
                          >
                            <X size={16} />
                          </button>
                        </div>


                        <div className="stat-grid">
                          <StatCard
                            icon={
                              <ShieldCheck />
                            }
                            label="Driver Safety Score"
                            value={
                              `${safetyScore.toFixed(0)}/100`
                            }
                            helper={
                              scoreInfo.label
                              ||
                              "Heuristic score"
                            }
                            tone={
                              safetyScore < 60
                                ? "danger"
                                : "neutral"
                            }
                          />

                          <StatCard
                            icon={
                              <Eye />
                            }
                            label="PERCLOS"
                            value={
                              `${Number(
                                detailInsights
                                  .perclos_percent
                                ||
                                0
                              ).toFixed(
                                1
                              )}%`
                            }
                            helper="Approx. time eyes closed"
                          />

                          <StatCard
                            icon={
                              <Activity />
                            }
                            label="Longest distraction"
                            value={
                              formatElapsedSeconds(
                                detailInsights
                                  .longest_confirmed_distraction_seconds
                              )
                            }
                            helper="Longest sustained away state"
                          />

                          <StatCard
                            icon={
                              <BellRing />
                            }
                            label="Critical alerts"
                            value={
                              detailInsights
                                .critical_alert_count
                              ??
                              0
                            }
                            helper="Critical safety events"
                          />
                        </div>


                        <div
                          style={{
                            marginTop: "12px",
                            padding: "12px 14px",
                            borderRadius: "12px",
                            background: "#f7faf8",
                            border: "1px solid #e4ebe7",
                            display: "flex",
                            alignItems: "flex-start",
                            gap: "10px",
                          }}
                        >
                          <Info
                            size={17}
                            style={{
                              marginTop: "2px",
                              flex: "0 0 auto",
                              color: "#1f8f63",
                            }}
                          />

                          <p
                            style={{
                              margin: 0,
                              color: "#65756f",
                              fontSize: "12px",
                              lineHeight: 1.6,
                            }}
                          >
                            The Driver Safety Score is a transparent
                            heuristic based on observed distraction,
                            drowsiness, eye closure, yawns and PERCLOS.
                            It is not an accident probability or a
                            medically validated risk score.
                          </p>
                        </div>
                      </section>


                      <section className="dashboard-grid">
                        <div className="panel chart-panel">
                          <div className="panel-heading">
                            <div>
                              <span className="kicker">
                                ATTENTION OVER TIME
                              </span>

                              <h3>
                                Driver attention timeline
                              </h3>
                            </div>

                            <span
                              style={{
                                fontSize: "12px",
                                color: "#7b8a84",
                              }}
                            >
                              {
                                detailSamples.length
                              }
                              {" "}telemetry samples
                            </span>
                          </div>


                          {attentionSeries.length > 0 ? (
                            <ResponsiveContainer
                              width="100%"
                              height={300}
                            >
                              <LineChart
                                data={
                                  attentionSeries
                                }
                              >
                                <CartesianGrid
                                  strokeDasharray="3 3"
                                  vertical={false}
                                />

                                <XAxis
                                  dataKey="elapsed"
                                  tickLine={false}
                                  axisLine={false}
                                  tickFormatter={
                                    (value) =>
                                      `${value}s`
                                  }
                                />

                                <YAxis
                                  domain={[0, 100]}
                                  tickLine={false}
                                  axisLine={false}
                                  tickFormatter={
                                    (value) =>
                                      `${value}`
                                  }
                                />

                                <Tooltip
                                  formatter={
                                    (
                                      value,
                                      name
                                    ) => {
                                      if (
                                        name
                                        ===
                                        "attention"
                                      ) {
                                        return [
                                          `${value}/100`,
                                          "Attention index",
                                        ];
                                      }

                                      return [
                                        value,
                                        name,
                                      ];
                                    }
                                  }

                                  labelFormatter={
                                    (value) =>
                                      `${value}s into drive`
                                  }
                                />

                                <Line
                                  type="monotone"
                                  dataKey="attention"
                                  name="attention"
                                  stroke="#1f8f63"
                                  strokeWidth={3}
                                  dot={false}
                                  isAnimationActive={false}
                                />
                              </LineChart>
                            </ResponsiveContainer>
                          ) : (
                            <div className="empty-state">
                              No telemetry samples were stored for this drive.
                            </div>
                          )}
                        </div>


                        <div className="panel">
                          <span className="kicker">
                            DRIVE SUMMARY
                          </span>

                          <h3>
                            Behaviour overview
                          </h3>

                          <div className="compact-list roomy">
                            <div>
                              <span>
                                Duration
                              </span>

                              <strong>
                                {
                                  formatDriveDuration(
                                    detailSummary
                                      .drive_duration_seconds
                                  )
                                }
                              </strong>
                            </div>

                            <div>
                              <span>
                                Safe / attentive
                              </span>

                              <strong>
                                {Number(
                                  detailSummary
                                    .attentive_percent
                                  ||
                                  0
                                ).toFixed(
                                  1
                                )}
                                %
                              </strong>
                            </div>

                            <div>
                              <span>
                                Confirmed distraction
                              </span>

                              <strong>
                                {Number(
                                  detailSummary
                                    .confirmed_distraction_percent
                                  ||
                                  0
                                ).toFixed(
                                  1
                                )}
                                %
                              </strong>
                            </div>

                            <div>
                              <span>
                                Most common away direction
                              </span>

                              <strong>
                                {
                                  detailInsights
                                    .most_common_away_direction
                                  ||
                                  "None"
                                }
                              </strong>
                            </div>

                            <div>
                              <span>
                                Drowsiness events
                              </span>

                              <strong>
                                {
                                  detailSummary
                                    .drowsiness_event_count
                                  ??
                                  0
                                }
                              </strong>
                            </div>

                            <div>
                              <span>
                                Yawns
                              </span>

                              <strong>
                                {
                                  detailSummary
                                    .yawn_count
                                  ??
                                  0
                                }
                              </strong>
                            </div>

                            <div>
                              <span>
                                Blinks
                              </span>

                              <strong>
                                {
                                  detailSummary
                                    .blink_count
                                  ??
                                  0
                                }
                              </strong>
                            </div>
                          </div>
                        </div>
                      </section>


                      <section className="panel">
                        <div className="panel-heading">
                          <div>
                            <span className="kicker">
                              SAFETY TIMELINE
                            </span>

                            <h3>
                              Detected drive events
                            </h3>
                          </div>

                          <span
                            style={{
                              fontSize: "12px",
                              color: "#7b8a84",
                            }}
                          >
                            {
                              detailEvents.length
                            }
                            {" "}events
                          </span>
                        </div>


                        {detailEvents.length > 0 ? (
                          <div className="compact-list roomy">
                            {
                              detailEvents.map(
                                (
                                  event,
                                  index
                                ) => {
                                  const type =
                                    String(
                                      event
                                        .event_type
                                      ||
                                      "EVENT"
                                    );

                                  const critical =
                                    type
                                      .toUpperCase()
                                      .includes(
                                        "CRITICAL"
                                      )
                                    ||
                                    String(
                                      event
                                        .message
                                      ||
                                      ""
                                    )
                                      .toUpperCase()
                                      .includes(
                                        "CRITICAL"
                                      );

                                  return (
                                    <div
                                      key={
                                        event.id
                                        ||
                                        `${event.elapsed_seconds}-${index}`
                                      }
                                      style={{
                                        borderLeft:
                                          `3px solid ${
                                            critical
                                              ? "#c13b3b"
                                              : "#1f8f63"
                                          }`,
                                        paddingLeft:
                                          "12px",
                                      }}
                                    >
                                      <span>
                                        {
                                          formatElapsedSeconds(
                                            event
                                              .elapsed_seconds
                                          )
                                        }
                                        {" • "}
                                        {
                                          type.replaceAll(
                                            "_",
                                            " "
                                          )
                                        }
                                      </span>

                                      <strong>
                                        {
                                          event.message
                                          ||
                                          type.replaceAll(
                                            "_",
                                            " "
                                          )
                                        }
                                      </strong>
                                    </div>
                                  );
                                }
                              )
                            }
                          </div>
                        ) : (
                          <div className="empty-state">
                            No significant safety events were recorded.
                          </div>
                        )}
                      </section>


                      <section
                        className="panel"
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          gap: "14px",
                          flexWrap: "wrap",
                        }}
                      >
                        <div>
                          <span className="kicker">
                            PRIVACY
                          </span>

                          <h3
                            style={{
                              marginBottom: "4px",
                            }}
                          >
                            Video is not stored
                          </h3>

                          <p
                            style={{
                              margin: 0,
                              color: "#6e7e78",
                              fontSize: "12px",
                              lineHeight: 1.6,
                            }}
                          >
                            NINO stores telemetry and safety events for
                            analytics. Camera frames are processed live
                            for inference and are not written to the
                            session database.
                          </p>
                        </div>

                        <ShieldCheck
                          size={28}
                          color="#1f8f63"
                        />
                      </section>
                    </section>
                  );
                })()}

              </>
            )}


        </main>

      </div>

    </div>
  );
}


export default App;
