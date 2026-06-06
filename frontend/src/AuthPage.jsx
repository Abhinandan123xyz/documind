import { useState } from "react"
import api from "./api"   // ← use the pre‑configured Axios instance

export default function AuthPage({ onLogin }) {
  const [mode, setMode]         = useState("login")
  const [email, setEmail]       = useState("")
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError]       = useState("")
  const [success, setSuccess]   = useState("")
  const [loading, setLoading]   = useState(false)

  const submit = async () => {
    setError("")
    setSuccess("")

    if (!email || !password) {
      setError("Email and password are required")
      return
    }
    if (!email.includes("@") || !email.includes(".")) {
      setError("Please enter a valid email address")
      return
    }
    if (password.length < 6) {
      setError("Password must be at least 6 characters")
      return
    }
    if (mode === "register" && !username.trim()) {
      setError("Username is required")
      return
    }

    setLoading(true)

    try {
      if (mode === "register") {
        const res = await api.post("/api/auth/register", {
          email, username, password
        })
        // Registration successful – user must verify email
        setSuccess(res.data.message || "Registration successful! Check your email (or the backend console) to verify your account, then log in.")
        setMode("login")
      } else {
        const form = new URLSearchParams()
        form.append("username", email)
        form.append("password", password)
        const res = await api.post("/api/auth/login", form, {
          headers: { "Content-Type": "application/x-www-form-urlencoded" }
        })
        localStorage.setItem("token", res.data.access_token)
        localStorage.setItem("user", JSON.stringify({
          id: res.data.user_id,
          username: res.data.username,
          email: res.data.email
        }))
        onLogin(res.data)
      }
    } catch (e) {
      console.log("Auth error:", e.response?.data)
      const detail = e.response?.data?.detail
      if (e.response?.status === 403) {
        setError(detail || "Please verify your email before logging in.")
      } else {
        setError(detail || "Something went wrong. Please try again.")
      }
    } finally {
      setLoading(false)
    }
  }

  const inputStyle = {
    padding: "11px 14px",
    background: "#0d1117",
    border: "1px solid #30363d",
    borderRadius: 8,
    color: "#e6edf3",
    fontSize: 14,
    outline: "none",
    width: "100%",
    boxSizing: "border-box"
  }

  return (
    <div style={{
      height: "100vh",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      background: "#0d0d0d",
      fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    }}>
      <div style={{
        width: 380,
        background: "#161b22",
        border: "1px solid #30363d",
        borderRadius: 12,
        padding: 40
      }}>
        <div style={{ textAlign: "center", marginBottom: 28 }}>
          <div style={{ fontSize: 48 }}>🧠</div>
          <h1 style={{ color: "#fff", fontSize: 22, fontWeight: 600, margin: "8px 0 4px" }}>
            DocuMind AI
          </h1>
          <p style={{ color: "#8b949e", fontSize: 13, margin: 0 }}>
            Your intelligent research assistant
          </p>
        </div>

        <div style={{
          display: "flex",
          border: "1px solid #30363d",
          borderRadius: 8,
          overflow: "hidden",
          marginBottom: 24
        }}>
          {["login", "register"].map(m => (
            <button key={m}
              onClick={() => { setMode(m); setError(""); setSuccess("") }}
              style={{
                flex: 1,
                padding: "10px",
                border: "none",
                cursor: "pointer",
                fontSize: 14,
                transition: "all 0.15s",
                background: mode === m ? "#21262d" : "transparent",
                color: mode === m ? "#fff" : "#8b949e",
                fontWeight: mode === m ? 500 : 400
              }}>
              {m === "login" ? "Sign In" : "Sign Up"}
            </button>
          ))}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <input
            type="email"
            placeholder="Email address"
            value={email}
            onChange={e => setEmail(e.target.value)}
            onKeyDown={e => e.key === "Enter" && submit()}
            style={inputStyle}
          />

          {mode === "register" && (
            <input
              type="text"
              placeholder="Username"
              value={username}
              onChange={e => setUsername(e.target.value)}
              onKeyDown={e => e.key === "Enter" && submit()}
              style={inputStyle}
            />
          )}

          <input
            type="password"
            placeholder="Password (min 6 characters)"
            value={password}
            onChange={e => setPassword(e.target.value)}
            onKeyDown={e => e.key === "Enter" && submit()}
            style={inputStyle}
          />

          {success && (
            <div style={{
              background: "#0d3320",
              border: "1px solid #1a5c3a",
              color: "#3fb950",
              padding: "10px 12px",
              borderRadius: 8,
              fontSize: 13
            }}>
              ✅ {success}
            </div>
          )}

          {error && (
            <div style={{
              background: "#3d1515",
              border: "1px solid #6e1b1b",
              color: "#f85149",
              padding: "10px 12px",
              borderRadius: 8,
              fontSize: 13
            }}>
              ⚠️ {error}
            </div>
          )}

          <button
            onClick={submit}
            disabled={loading}
            style={{
              padding: 12,
              background: loading ? "#1a4a1a" : "#238636",
              border: "none",
              borderRadius: 8,
              color: "white",
              fontSize: 15,
              fontWeight: 500,
              cursor: loading ? "not-allowed" : "pointer",
              marginTop: 4,
              transition: "background 0.15s",
              width: "100%"
            }}
          >
            {loading ? "Please wait..." : mode === "login" ? "Sign In" : "Create Account"}
          </button>
        </div>

        <p style={{ textAlign: "center", fontSize: 11, color: "#484f58", marginTop: 24 }}>
          Powered by Groq LLaMA 3.3 · RAG · ChromaDB
        </p>
      </div>
    </div>
  )
}