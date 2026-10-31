
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
  ChevronDown,
  CircleUserRound,
  Gauge,
  History,
  LogOut,
  Menu,
  Moon,
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


/* =========================================================
   LOGIN
========================================================= */

function Login({
  onLogin,
}) {
  const [mode, setMode] =
    useState("signin");

  const [fullName, setFullName] =
    useState("");

  const [email, setEmail] =
    useState("");

  const [password, setPassword] =
    useState("");

  const [confirmPassword, setConfirmPassword] =
    useState("");

  const [error, setError] =
    useState("");

  const [message, setMessage] =
    useState("");

  const [busy, setBusy] =
    useState(false);


  async function loadBackendUser(
    accessToken
  ) {
    sessionStorage.setItem(
      "nino_token",
      accessToken
    );

    const response =
      await fetch(
        `${API_BASE}/api/auth/me`,
        {
          headers: {
            Authorization:
              `Bearer ${accessToken}`,
          },
        }
      );

    let data = {};

    try {
      data = await response.json();
    } catch {
      data = {};
    }

    if (!response.ok) {
      throw new Error(
        data.detail ||
        "NINO backend authentication failed."
      );
    }

    onLogin(data);
  }


  async function submit(
    event
  ) {
    event.preventDefault();

    setBusy(true);
    setError("");
    setMessage("");

    try {
      const cleanEmail =
        email.trim().toLowerCase();

      if (!cleanEmail) {
        throw new Error(
          "Enter your email address."
        );
      }

      if (password.length < 6) {
        throw new Error(
          "Password must be at least 6 characters."
        );
      }

      if (mode === "signup") {
        if (!fullName.trim()) {
          throw new Error(
            "Enter your full name."
          );
        }

        if (
          password !==
          confirmPassword
        ) {
          throw new Error(
            "Passwords do not match."
          );
        }

        const {
          data,
          error: signUpError,
        } = await supabase.auth.signUp({
          email: cleanEmail,
          password,
          options: {
            data: {
              full_name:
                fullName.trim(),
              role: "Driver",
            },
            emailRedirectTo:
              window.location.origin,
          },
        });

        if (signUpError) {
          throw signUpError;
        }

        if (!data.session) {
          setMessage(
            "Account created. Check your email to confirm your NINO account, then sign in."
          );

          setMode("signin");
          setPassword("");
          setConfirmPassword("");
          return;
        }

        await loadBackendUser(
          data.session.access_token
        );

        return;
      }


      const {
        data,
        error: signInError,
      } = await supabase.auth
        .signInWithPassword({
          email: cleanEmail,
          password,
        });

      if (signInError) {
        throw signInError;
      }

      if (!data.session) {
        throw new Error(
          "No login session was returned."
        );
      }

      await loadBackendUser(
        data.session.access_token
      );

    } catch (error) {
      setError(
        error.message ||
        "Authentication failed."
      );

    } finally {
      setBusy(false);
    }
  }


  function changeMode(
    nextMode
  ) {
    setMode(nextMode);
    setError("");
    setMessage("");
    setPassword("");
    setConfirmPassword("");
  }


  return (
    <div className="auth-shell">

      <section className="auth-hero">

        <div className="auth-brand">
          <div className="logo-mark">
            N
          </div>

          <div>
            <strong>NINO</strong>

            <span>
              Driver Safety Intelligence
            </span>
          </div>
        </div>


        <div className="auth-copy">

          <span className="kicker">
            AI DRIVER SAFETY
          </span>

          <h1>
            Intelligence that watches
            the road with you.
          </h1>

          <p>
            Real-time computer vision,
            Random Forest classification,
            driver-state analytics and
            intelligent safety alerts.
          </p>


          <div className="auth-feature-grid">

            <article>
              <Camera size={20} />

              <div>
                <strong>
                  Real-time vision
                </strong>

                <span>
                  Browser-native camera preview
                </span>
              </div>
            </article>


            <article>
              <BrainCircuit size={20} />

              <div>
                <strong>
                  Machine learning
                </strong>

                <span>
                  5-class head direction
                </span>
              </div>
            </article>


            <article>
              <ShieldCheck size={20} />

              <div>
                <strong>
                  Safety alerts
                </strong>

                <span>
                  Drowsiness and distraction
                </span>
              </div>
            </article>


            <article>
              <BarChart3 size={20} />

              <div>
                <strong>
                  Personal drive analytics
                </strong>

                <span>
                  Secure user-specific history
                </span>
              </div>
            </article>

          </div>

        </div>

      </section>


      <section className="auth-panel">

        <form
          className="auth-card"
          onSubmit={submit}
        >
          <span className="kicker">
            NINO ACCOUNT
          </span>

          <h2>
            {mode === "signup"
              ? "Create your account"
              : "Welcome back"}
          </h2>

          <p>
            {mode === "signup"
              ? "Create a secure driver profile to save your drive history."
              : "Sign in to open your driver monitoring console."}
          </p>


          <div
            style={{
              display: "grid",
              gridTemplateColumns:
                "1fr 1fr",
              gap: "8px",
              marginBottom: "12px",
            }}
          >
            <button
              type="button"
              className={
                mode === "signin"
                  ? "btn primary"
                  : "btn secondary"
              }
              onClick={() =>
                changeMode(
                  "signin"
                )
              }
            >
              Sign in
            </button>

            <button
              type="button"
              className={
                mode === "signup"
                  ? "btn primary"
                  : "btn secondary"
              }
              onClick={() =>
                changeMode(
                  "signup"
                )
              }
            >
              Register
            </button>
          </div>


          {mode === "signup" && (
            <label>
              Full name

              <input
                type="text"
                autoComplete="name"
                value={fullName}
                onChange={
                  (event) =>
                    setFullName(
                      event.target.value
                    )
                }
                placeholder="Your full name"
              />
            </label>
          )}


          <label>
            Email

            <input
              type="email"
              autoComplete="email"
              value={email}
              onChange={
                (event) =>
                  setEmail(
                    event.target.value
                  )
              }
              placeholder="you@example.com"
            />
          </label>


          <label>
            Password

            <input
              type="password"
              autoComplete={
                mode === "signup"
                  ? "new-password"
                  : "current-password"
              }
              value={password}
              onChange={
                (event) =>
                  setPassword(
                    event.target.value
                  )
              }
              placeholder="Minimum 6 characters"
            />
          </label>


          {mode === "signup" && (
            <label>
              Confirm password

              <input
                type="password"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={
                  (event) =>
                    setConfirmPassword(
                      event.target.value
                    )
                }
                placeholder="Repeat password"
              />
            </label>
          )}


          {error && (
            <div className="auth-error">
              {error}
            </div>
          )}


          {message && (
            <div
              className="notice"
              style={{
                margin: "0 0 12px",
              }}
            >
              {message}
            </div>
          )}


          <button
            className="btn primary wide"
            disabled={busy}
          >
            {busy
              ? "Please wait..."
              : mode === "signup"
              ? "Create NINO account"
              : "Sign in"}
          </button>


          <div className="demo-credentials">
            <span>
              Secure authentication
            </span>

            <strong>
              Powered by Supabase Auth
            </strong>

            <span>
              Your password is not stored by NINO.
            </span>
          </div>

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

      <div>
        <span>
          {label}
        </span>

        <strong>
          {value}
        </strong>

        {helper && (
          <small>
            {helper}
          </small>
        )}
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
    useState({
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
      distraction_state: "ATTENTIVE",
      distraction_duration: 0,
      alert_state: "NORMAL",
      events: [],
    });

  const [liveSeries, setLiveSeries] =
    useState([]);


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

      setLiveState(
        (
          current
        ) => ({
          ...current,

          drive_active:
            true,

          session_id:
            data.session_id,
        })
      );

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
        (
          current
        ) => ({
          ...current,

          connected:
            false,

          drive_active:
            false,

          session_id:
            null,
        })
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

    setLiveState({
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
      distraction_state: "ATTENTIVE",
      distraction_duration: 0,
      alert_state: "NORMAL",
      events: [],
    });
  }


  /* =====================================================
     INITIAL LOAD / PAGE CLEANUP
  ===================================================== */

  useEffect(
    () => {
      bootstrap();

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


  /* =====================================================
     LOGIN SCREEN
  ===================================================== */

  if (!user) {
    return (
      <Login
        onLogin={
          setUser
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
        "model",

      label:
        "ML model",

      icon:
        <BrainCircuit size={18} />,
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

          {navItems.map(
            (
              item
            ) => (
              <button
                key={
                  item.id
                }

                className={
                  page
                  ===
                  item.id
                    ? "nav-link active"
                    : "nav-link"
                }

                onClick={() => {
                  setPage(
                    item.id
                  );

                  setSidebarOpen(
                    false
                  );
                }}
              >
                {
                  item.icon
                }

                <span>
                  {
                    item.label
                  }
                </span>
              </button>
            )
          )}

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

            {driveActive
              ? "Drive monitoring live"
              : socketReady
              ? "AI connected"
              : "Monitoring idle"}
          </div>

          <small>
            Browser camera + WebSocket inference
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
                }
              </h1>
            </div>

          </div>


          <div className="topbar-actions">

            <button
              className="icon-btn"

              onClick={
                () =>
                  Promise.all([
                    loadSummary(),
                    loadSessions(),
                    loadModelInfo(),
                  ])
              }

              title="Refresh"
            >
              <RefreshCcw
                size={17}
              />
            </button>


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
                  {user.name
                    .charAt(0)
                    .toUpperCase()}
                </div>

                <div>
                  <strong>
                    {
                      user.name
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
                          user.name
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
                      : `Welcome back, ${user.name.split(
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
                        <div className="camera-empty">
                          <Camera
                            size={38}
                          />

                          <strong>
                            Camera ready
                          </strong>

                          <span>
                            Start a drive to
                            begin instant browser
                            monitoring.
                          </span>
                        </div>
                      )}

                    </div>

                  </div>


                  <div className="live-status panel">

                    <span className="kicker">
                      {driveActive
                        ? "LIVE DRIVER STATE"
                        : "LAST / CURRENT STATE"}
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
                          {
                            liveState
                              .alert_state
                            ||
                            "NORMAL"
                          }
                        </strong>

                        <span>
                          Current safety state
                        </span>
                      </div>

                    </div>


                    <div className="compact-list">

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
                          ML confidence
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

                        <strong>
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
                          Distraction
                        </span>

                        <strong>
                          {
                            liveState
                              .distraction_state
                            ||
                            "—"
                          }
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

                        label="Head orientation away"

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

                        helper="Includes brief glances"
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
                          <Moon />
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
                          RF confidence
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

                        <strong>
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

                        <strong>
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

                        <strong>
                          {liveState
                            .face_detected
                            ? "DETECTED"
                            : "NOT DETECTED"}
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
                          Eye / mouth features
                        </h3>
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
                      `${Number(
                        summary
                          ?.drive_duration_seconds
                        ||
                        0
                      ).toFixed(
                        1
                      )} s`
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

                    label="Head orientation away"

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
                      <Moon />
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
              ML MODEL
          ================================================== */}

          {page ===
            "model"
            &&
            (
              <>
                <SectionTitle
                  eyebrow="MACHINE LEARNING"

                  title="Model laboratory"
                />


                <section className="model-hero panel">

                  <div>
                    <span className="kicker">
                      HEAD-DIRECTION CLASSIFIER
                    </span>

                    <h2>
                      {
                        modelInfo
                          ?.model
                        ||
                        "Random Forest Classifier"
                      }
                    </h2>

                    <p>
                      Five-class head-direction
                      classification using
                      MediaPipe facial landmarks,
                      ALIGNED_XYZ feature
                      engineering and temporal
                      smoothing for real-time
                      driver monitoring.
                    </p>
                  </div>


                  <BrainCircuit
                    size={64}
                  />

                </section>


                <section className="stat-grid">

                  <StatCard
                    icon={
                      <Gauge />
                    }

                    label="Cross-session accuracy"

                    value={
                      `${(
                        Number(
                          modelInfo
                            ?.cross_session_accuracy
                          ||
                          0
                        )
                        *
                        100
                      ).toFixed(
                        2
                      )}%`
                    }
                  />


                  <StatCard
                    icon={
                      <BarChart3 />
                    }

                    label="Macro F1"

                    value={
                      `${(
                        Number(
                          modelInfo
                            ?.macro_f1
                          ||
                          0
                        )
                        *
                        100
                      ).toFixed(
                        2
                      )}%`
                    }
                  />


                  <StatCard
                    icon={
                      <BrainCircuit />
                    }

                    label="Features"

                    value={
                      modelInfo
                        ?.feature_count
                      ??
                      36
                    }

                    helper="ALIGNED_XYZ"
                  />


                  <StatCard
                    icon={
                      <Activity />
                    }

                    label="Training samples"

                    value={
                      modelInfo
                        ?.training_samples
                      ??
                      1322
                    }

                    helper="3 collection sessions"
                  />

                </section>


                <section className="panel">

                  <div className="panel-heading">

                    <div>
                      <span className="kicker">
                        FEATURE ENGINEERING
                      </span>

                      <h3>
                        ML pipeline
                      </h3>
                    </div>


                    <span className="model-chip">
                      {
                        modelInfo
                          ?.representation
                        ||
                        "ALIGNED_XYZ"
                      }
                    </span>

                  </div>


                  <div className="pipeline">

                    {(
                      modelInfo
                        ?.pipeline
                      ||
                      []
                    ).map(
                      (
                        step,
                        index
                      ) => (
                        <div
                          className="pipeline-step"

                          key={
                            step
                          }
                        >
                          <span>
                            {
                              index
                              +
                              1
                            }
                          </span>

                          <strong>
                            {
                              step
                            }
                          </strong>
                        </div>
                      )
                    )}

                  </div>

                </section>


                <section className="panel">

                  <span className="kicker">
                    VALIDATION LIMITATION
                  </span>

                  <h3>
                    Scientific interpretation
                  </h3>

                  <p
                    style={{
                      color:
                        "#6e7e78",

                      lineHeight:
                        1.7,

                      fontSize:
                        "12px",
                    }}
                  >
                    {
                      modelInfo
                        ?.validation_note
                      ||
                      "Current validation is cross-session and controlled; unseen-person validation remains future work."
                    }
                  </p>

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


                <section className="panel table-panel">

                  <div className="table-head">

                    <span>
                      Session
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


                  {sessions.length
                    ===
                    0
                    ? (
                      <div className="empty-state">
                        No analyzed sessions
                        available.
                      </div>
                    )
                    :
                    sessions.map(
                      (
                        session
                      ) => (
                        <div
                          className="table-row"

                          key={
                            session
                              .session_id
                          }
                        >
                          <strong>
                            {
                              session
                                .session_id
                            }
                          </strong>

                          <span>
                            {Number(
                              session
                                .drive_duration_seconds
                              ||
                              0
                            ).toFixed(
                              1
                            )}
                            {" "}s
                          </span>

                          <span>
                            {Number(
                              session
                                .attentive_percent
                              ||
                              0
                            ).toFixed(
                              1
                            )}
                            %
                          </span>

                          <span>
                            {
                              session
                                .distraction_event_count
                              ??
                              0
                            }
                          </span>

                          <span>
                            {
                              session
                                .total_safety_alerts
                              ??
                              0
                            }
                          </span>
                        </div>
                      )
                    )}

                </section>

              </>
            )}


          <footer className="app-footer">
            NINO is an academic
            AI-assisted driver-monitoring
            prototype. Metrics represent
            detected behaviour, not accident
            probability.
          </footer>

        </main>

      </div>

    </div>
  );
}


export default App;
