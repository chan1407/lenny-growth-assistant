import { useEffect, useRef, useState } from "react";
import "./App.css";

function renderMarkdown(markdown) {
  return markdown.split("\n").map((line, index) => {
    const parts = line.split(/(\*\*.*?\*\*)/g).map((part, partIndex) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return <strong key={partIndex}>{part.slice(2, -2)}</strong>;
      }
      return part;
    });

    if (line.startsWith("# ")) return <h2 key={index}>{parts.slice(1)}</h2>;
    if (line.startsWith("## ")) return <h3 key={index}>{parts.slice(1)}</h3>;
    if (line.startsWith("- ") || line.startsWith("* ")) {
      return <li key={index}>{parts.slice(1)}</li>;
    }
    if (!line.trim()) return <div className="markdown-spacer" key={index} />;
    return <p key={index}>{parts}</p>;
  });
}

function cleanSourceText(value) {
  return String(value || "")
    .replace(/\*\*/g, "")
    .replace(/\[https?:\/\/[^\]]+\]\((https?:\/\/[^)]+)\)/g, "$1")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
}

function sourceKey(source) {
  return [
    cleanSourceText(source?.title),
    cleanSourceText(source?.guest),
    cleanSourceText(source?.youtube_url),
    cleanSourceText(source?.publish_date),
  ].join("||");
}

function uniqueSources(sources = []) {
  const seen = new Set();
  return sources.filter((source) => {
    const key = sourceKey(source);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function App() {
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState([]);
  const [llm, setLlm] = useState({ provider: "ollama", model: "llama3.2:3b" });
  const [sessionId, setSessionId] = useState(null);
  const [skillLoading, setSkillLoading] = useState(false);
  const [artifact, setArtifact] = useState(null);
  const [artifactPrompt, setArtifactPrompt] = useState("");
  const [artifactFormat, setArtifactFormat] = useState("markdown");
  const [artifactLoading, setArtifactLoading] = useState(false);
  const [artifactError, setArtifactError] = useState("");

  const sessionIdRef = useRef(null);
  const sessionPromiseRef = useRef(null);

  const ensureSession = async () => {
    if (sessionIdRef.current) {
      return sessionIdRef.current;
    }

    if (!sessionPromiseRef.current) {
      sessionPromiseRef.current = fetch("http://127.0.0.1:8000/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      })
        .then((response) => response.json())
        .then((data) => {
          if (!data.session_id) {
            throw new Error("The backend did not return a session ID.");
          }

          sessionIdRef.current = data.session_id;
          setSessionId(data.session_id);
          return data.session_id;
        })
        .catch((error) => {
          sessionPromiseRef.current = null;
          throw error;
        });
    }

    return sessionPromiseRef.current;
  };

  useEffect(() => {
    fetch("http://127.0.0.1:8000/health")
      .then((response) => response.json())
      .then((data) => {
        if (data.llm) setLlm(data.llm);
      })
      .catch(() => {});

    ensureSession().catch(() => {});
  }, []);

  const sendMessage = async () => {
    if (!message.trim()) return;

    const userMessage = message;

    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);

    setMessage("");

    try {
      const currentSessionId = await ensureSession();

      const response = await fetch("http://127.0.0.1:8000/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: userMessage,
          session_id: currentSessionId,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.message || "The configured provider could not answer.",
        );
      }

      setLlm({ provider: data.provider, model: data.model });

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.answer,
          sources: Array.isArray(data.sources) ? data.sources : [],
        },
      ]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: error.message || "Unable to connect to the backend.",
        },
      ]);
    }
  };

  const generateShip30 = async () => {
    const currentQuestion =
      message.trim() ||
      [...messages].reverse().find((item) => item.role === "user")?.content;
    if (!currentQuestion || skillLoading) return;

    setSkillLoading(true);
    try {
      const currentSessionId = await ensureSession();

      const response = await fetch("http://127.0.0.1:8000/skills/ship30", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: currentQuestion,
          session_id: currentSessionId,
        }),
      });
      const data = await response.json();
      if (!response.ok)
        throw new Error(data.message || "The essay skill failed.");
      setLlm({ provider: data.provider, model: data.model });
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.essay,
          skill: `${data.skill_name} v${data.skill_version}`,
          sources: data.sources,
        },
      ]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: error.message || "Unable to generate the essay.",
        },
      ]);
    } finally {
      setSkillLoading(false);
    }
  };

  const generateArtifact = async () => {
    if (!artifactPrompt.trim() || artifactLoading) return;

    setArtifactLoading(true);
    setArtifactError("");
    try {
      const currentSessionId = await ensureSession();

      const response = await fetch("http://127.0.0.1:8000/artifacts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: currentSessionId,
          prompt: artifactPrompt.trim(),
          format: artifactFormat,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.message || "The artifact could not be generated.");
      }
      setArtifact(data);
      setLlm({ provider: data.provider, model: data.model });
    } catch (error) {
      setArtifactError(error.message || "Unable to generate the artifact.");
    } finally {
      setArtifactLoading(false);
    }
  };

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>Lenny Growth Assistant</h1>
          <p>Product & growth insights grounded in Lenny's knowledge</p>
        </div>

        <div className="model" title="Active LLM provider and model">
          ● {llm.provider} / {llm.model}
        </div>
      </header>

      <div className="workspace">
        <main className="chat">
          {messages.length === 0 && (
            <div className="welcome">
              <h2>What can I help you with?</h2>
              <p>
                Ask about product, growth, onboarding, retention,
                experimentation and more.
              </p>
            </div>
          )}

          {messages.map((msg, index) => (
            <div key={index} className={`message ${msg.role}`}>
              <div className="role">
                {msg.role === "user" ? "You" : "Lenny"}
              </div>
              <div className="content">
                {msg.role === "assistant"
                  ? renderMarkdown(msg.content)
                  : msg.content}
                {msg.skill && <div className="skill-label">{msg.skill}</div>}
                {msg.role === "assistant" && msg.sources?.length > 0 && (
                  <div className="message-sources">
                    <div className="message-sources-title">Sources</div>
                    <ul className="message-sources-list">
                      {uniqueSources(msg.sources).map((source, sourceIndex) => {
                        const title = cleanSourceText(source.title);
                        const guest = cleanSourceText(source.guest);
                        const url = cleanSourceText(source.youtube_url);
                        const date = cleanSourceText(source.publish_date);

                        return (
                          <li
                            key={`${sourceIndex}-${sourceKey(source)}`}
                            className="message-source-card"
                          >
                            <div className="message-source-title">
                              {title || guest || "Transcript source"}
                            </div>
                            <div className="message-source-meta">
                              {guest && (
                                <span className="message-source-guest">
                                  {guest}
                                </span>
                              )}
                              {date && (
                                <span className="message-source-date">
                                  {date}
                                </span>
                              )}
                              {url && (
                                <a
                                  className="message-source-link"
                                  href={url}
                                  target="_blank"
                                  rel="noreferrer"
                                >
                                  YouTube
                                </a>
                              )}
                            </div>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          ))}
        </main>

        <aside className="artifact-viewer" aria-label="Artifact Viewer">
          <div className="artifact-header">
            <div>
              <span className="eyebrow">Workspace</span>
              <h2>Artifact Viewer</h2>
            </div>
            {artifact && (
              <span className="artifact-format">{artifact.format}</span>
            )}
          </div>

          <label className="artifact-label" htmlFor="artifact-prompt">
            Create from this conversation
          </label>
          <textarea
            id="artifact-prompt"
            className="artifact-prompt"
            value={artifactPrompt}
            onChange={(event) => setArtifactPrompt(event.target.value)}
            placeholder="e.g. Turn the key onboarding insight into a one-page brief"
          />
          <div className="artifact-controls">
            <select
              value={artifactFormat}
              onChange={(event) => setArtifactFormat(event.target.value)}
              aria-label="Artifact format"
            >
              <option value="markdown">Markdown</option>
              <option value="html">HTML preview</option>
            </select>
            <button
              className="artifact-generate"
              onClick={generateArtifact}
              disabled={!sessionId || !artifactPrompt.trim() || artifactLoading}
            >
              {artifactLoading ? "Generating..." : "Generate"}
            </button>
          </div>

          {artifactError && (
            <div className="artifact-error">{artifactError}</div>
          )}

          {!artifact && !artifactLoading && !artifactError && (
            <div className="artifact-empty">
              Generate a Markdown brief or an isolated HTML preview from the
              current session.
            </div>
          )}

          {artifactLoading && (
            <div className="artifact-empty">Preparing your artifact...</div>
          )}

          {artifact && !artifactLoading && (
            <div className="artifact-result">
              <h3>{artifact.title}</h3>
              {artifact.format === "html" ? (
                <iframe
                  className="artifact-frame"
                  title={artifact.title}
                  sandbox=""
                  referrerPolicy="no-referrer"
                  srcDoc={artifact.content}
                />
              ) : (
                <div className="artifact-markdown">
                  {renderMarkdown(artifact.content)}
                </div>
              )}
              <details className="artifact-source">
                <summary>View source</summary>
                <pre>{artifact.content}</pre>
              </details>
              {artifact.sources?.length > 0 && (
                <div className="artifact-sources">
                  Sources:{" "}
                  {artifact.sources
                    .map((source) => source.guest || source.title)
                    .join(", ")}
                </div>
              )}
            </div>
          )}
        </aside>
      </div>

      <div className="input-area">
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              sendMessage();
            }
          }}
          placeholder="Ask a product or growth question..."
        />

        <button onClick={sendMessage}>Send</button>
        <button
          className="skill-button"
          onClick={generateShip30}
          disabled={skillLoading}
        >
          {skillLoading ? "Writing..." : "Ship 30 essay"}
        </button>
      </div>
    </div>
  );
}

export default App;
