import React, { useEffect, useMemo, useRef, useState } from "react";
import { Route, Routes, useNavigate } from "react-router-dom";
import { apiFetch } from "./api.js";

function useAuth() {
  const [role, setRole] = useState(localStorage.getItem("role") || "");
  const [token, setToken] = useState(localStorage.getItem("access_token") || "");

  const login = (accessToken, userRole) => {
    localStorage.setItem("access_token", accessToken);
    localStorage.setItem("role", userRole);
    setToken(accessToken);
    setRole(userRole);
  };

  const logout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("role");
    setToken("");
    setRole("");
  };

  return { role, token, login, logout };
}

function LoginPage({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    try {
      const data = await apiFetch("/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password })
      });
      onLogin(data.access_token, data.role);
      navigate(data.role === "admin" ? "/admin" : "/candidate");
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="page">
      <form className="card" onSubmit={handleSubmit}>
        <h1>QA Assessment Platform</h1>
        <p>Sign in to continue.</p>
        {error && <div className="error">{error}</div>}
        <label>
          Username
          <input value={username} onChange={(e) => setUsername(e.target.value)} />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        <button type="submit">Login</button>
      </form>
    </div>
  );
}

function AdminDashboard({ onLogout }) {
  const [users, setUsers] = useState([]);
  const [tests, setTests] = useState([]);
  const [testTypes, setTestTypes] = useState([]);
  const [questionSets, setQuestionSets] = useState([]);
  const [questionSetQuestions, setQuestionSetQuestions] = useState([]);
  const [activeQuestionSetId, setActiveQuestionSetId] = useState("");
  const [editingQuestion, setEditingQuestion] = useState(null);
  const [dashboardRows, setDashboardRows] = useState([]);
  const [summaryExpanded, setSummaryExpanded] = useState({});
  const [summaryHistoryExpanded, setSummaryHistoryExpanded] = useState({});
  const [userManageOpenId, setUserManageOpenId] = useState(null);
  const [createUserOpen, setCreateUserOpen] = useState(false);
  const [testTypesOpen, setTestTypesOpen] = useState(false);
  const [createQuestionSetOpen, setCreateQuestionSetOpen] = useState(false);
  const [questionEditorOpen, setQuestionEditorOpen] = useState(false);
  const [actionModal, setActionModal] = useState({
    open: false,
    type: "",
    user: null
  });
  const [successMessage, setSuccessMessage] = useState("");
  const [toastMessage, setToastMessage] = useState("");
  const [monitoring, setMonitoring] = useState(null);
  const [error, setError] = useState("");
  const [filters, setFilters] = useState({
    testType: "",
    status: "",
    violationsOnly: false
  });
  const [activeTab, setActiveTab] = useState("summary");
  const [assignedSetByUser, setAssignedSetByUser] = useState({});
  const [submissionView, setSubmissionView] = useState({
    open: false,
    rows: [],
    reviewed: {}
  });

  const [newUser, setNewUser] = useState({
    username: "",
    password: "",
    role: "candidate"
  });
  const [newTest, setNewTest] = useState({
    title: "",
    test_type_id: "",
    question_set_id: "",
    duration_minutes: 60,
    warning_minutes: 5
  });
  const [newTestType, setNewTestType] = useState({ name: "" });
  const [newQuestionSet, setNewQuestionSet] = useState({
    name: "",
    test_type_id: "",
    description: "",
    duration_minutes: 60,
    warning_minutes: 5
  });
  const [editQuestionSet, setEditQuestionSet] = useState(null);
  const [newQuestion, setNewQuestion] = useState({
    title: "",
    body: "",
    sections: ""
  });
  const [answerType, setAnswerType] = useState("long_text");
  const [allowMultiple, setAllowMultiple] = useState(false);
  const [options, setOptions] = useState([{ option_text: "", is_correct: false }]);

  const loadData = async () => {
    try {
      const [usersData, testsData, monitoringData, typesData, setsData] =
        await Promise.all([
          apiFetch("/admin/users"),
          apiFetch("/admin/tests"),
          apiFetch("/admin/monitoring"),
          apiFetch("/admin/test-types"),
          apiFetch("/admin/question-sets")
        ]);
      setUsers(usersData);
      setTests(testsData);
      setMonitoring(monitoringData);
      setTestTypes(typesData);
      setQuestionSets(setsData);
    } catch (err) {
      setError(err.message);
    }
  };

  const loadDashboard = async (nextFilters = filters) => {
    const params = new URLSearchParams();
    if (nextFilters.testType) params.set("test_type", nextFilters.testType);
    if (nextFilters.status) params.set("status", nextFilters.status);
    if (nextFilters.violationsOnly) params.set("violations_only", "true");
    try {
      const data = await apiFetch(`/admin/dashboard?${params.toString()}`);
      setDashboardRows(data.candidates || []);
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    loadData();
    loadDashboard();
  }, []);

  const handleCreateUser = async (event) => {
    event.preventDefault();
    setError("");
    try {
      await apiFetch("/admin/users", {
        method: "POST",
        body: JSON.stringify(newUser)
      });
      setNewUser({ username: "", password: "", role: "candidate" });
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleCreateTest = async (event) => {
    event.preventDefault();
    setError("");
    try {
      const duration = Number(newTest.duration_minutes);
      const warning = Number(newTest.warning_minutes);
      if (warning >= duration) {
        setError("Warning must be less than duration.");
        return;
      }
      await apiFetch("/admin/tests", {
        method: "POST",
        body: JSON.stringify({
          ...newTest,
          test_type_id: Number(newTest.test_type_id),
          question_set_id: Number(newTest.question_set_id),
          duration_minutes: duration,
          warning_minutes: warning
        })
      });
      setNewTest({
        title: "",
        test_type_id: "",
        question_set_id: "",
        duration_minutes: 60,
        warning_minutes: 5
      });
      await loadData();
      await loadDashboard();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleCreateTestType = async (event) => {
    event.preventDefault();
    setError("");
    try {
      await apiFetch("/admin/test-types", {
        method: "POST",
        body: JSON.stringify(newTestType)
      });
      setNewTestType({ name: "" });
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  };

  const toggleTestActive = async (testId, isActive) => {
    try {
      await apiFetch(`/admin/tests/${testId}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: isActive })
      });
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleCreateQuestionSet = async (event) => {
    event.preventDefault();
    setError("");
    try {
      await apiFetch("/admin/question-sets", {
        method: "POST",
        body: JSON.stringify({
          ...newQuestionSet,
          test_type_id: Number(newQuestionSet.test_type_id),
          duration_minutes: Number(newQuestionSet.duration_minutes),
          warning_minutes: Number(newQuestionSet.warning_minutes)
        })
      });
      setNewQuestionSet({
        name: "",
        test_type_id: "",
        description: "",
        duration_minutes: 60,
        warning_minutes: 5
      });
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  };

  const loadQuestionSetQuestions = async (setId) => {
    if (!setId) {
      setQuestionSetQuestions([]);
      return;
    }
    try {
      const data = await apiFetch(`/admin/question-sets/${setId}/questions`);
      setQuestionSetQuestions(data);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleUpdateQuestionSet = async (event) => {
    event.preventDefault();
    if (!editQuestionSet) return;
    try {
      await apiFetch(`/admin/question-sets/${editQuestionSet.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: editQuestionSet.name,
          description: editQuestionSet.description,
          test_type_id: Number(editQuestionSet.test_type_id),
          duration_minutes: Number(editQuestionSet.duration_minutes),
          warning_minutes: Number(editQuestionSet.warning_minutes)
        })
      });
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleCreateQuestion = async (event) => {
    event.preventDefault();
    setError("");
    if (!activeQuestionSetId) {
      setError("Select a question set first.");
      return;
    }
    try {
      if (editingQuestion) {
        await apiFetch(
          `/admin/question-sets/${activeQuestionSetId}/questions/${editingQuestion.id}`,
          {
            method: "PATCH",
            body: JSON.stringify({
              ...newQuestion,
              answer_type: answerType,
              allow_multiple: allowMultiple,
              options: answerType === "multiple_choice" ? options : []
            })
          }
        );
      } else {
        await apiFetch(`/admin/question-sets/${activeQuestionSetId}/questions`, {
          method: "POST",
          body: JSON.stringify({
            ...newQuestion,
            answer_type: answerType,
            allow_multiple: allowMultiple,
            options: answerType === "multiple_choice" ? options : []
          })
        });
      }
      setNewQuestion({ title: "", body: "", sections: "" });
      setAnswerType("long_text");
      setAllowMultiple(false);
      setOptions([{ option_text: "", is_correct: false }]);
      setEditingQuestion(null);
      setQuestionEditorOpen(false);
      await loadQuestionSetQuestions(activeQuestionSetId);
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  };


  const handleQuestionSetOrderSave = async () => {
    if (!activeQuestionSetId) return;
    try {
      await apiFetch(`/admin/question-sets/${activeQuestionSetId}/order`, {
        method: "POST",
        body: JSON.stringify({
          question_ids: questionSetQuestions.map((q) => q.id)
        })
      });
      await loadQuestionSetQuestions(activeQuestionSetId);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleQuestionSetDragStart = (index) => (event) => {
    event.dataTransfer.setData("text/plain", String(index));
  };

  const handleQuestionSetDrop = (index) => (event) => {
    event.preventDefault();
    const fromIndex = Number(event.dataTransfer.getData("text/plain"));
    if (Number.isNaN(fromIndex)) return;
    setQuestionSetQuestions((prev) => {
      const next = [...prev];
      const [moved] = next.splice(fromIndex, 1);
      next.splice(index, 0, moved);
      return next;
    });
  };

  const handleQuestionSelect = (question) => {
    setEditingQuestion(question);
    setQuestionEditorOpen(true);
    setNewQuestion({
      title: question.title,
      body: question.body,
      sections: question.sections || ""
    });
    setAnswerType(question.answer_type);
    setAllowMultiple(question.allow_multiple);
    setOptions(
      question.options.length > 0
        ? question.options.map((opt) => ({
            option_text: opt.option_text,
            is_correct: opt.is_correct
          }))
        : [{ option_text: "", is_correct: false }]
    );
  };

  const handleQuestionDelete = async (questionId) => {
    if (!activeQuestionSetId) return;
    try {
      await apiFetch(
        `/admin/question-sets/${activeQuestionSetId}/questions/${questionId}`,
        { method: "DELETE" }
      );
      await loadQuestionSetQuestions(activeQuestionSetId);
      setEditingQuestion(null);
    } catch (err) {
      setError(err.message);
    }
  };

  const addOption = () =>
    setOptions((prev) => [...prev, { option_text: "", is_correct: false }]);
  const updateOption = (index, value) => {
    setOptions((prev) =>
      prev.map((opt, idx) =>
        idx === index ? { ...opt, option_text: value } : opt
      )
    );
  };
  const toggleCorrect = (index) => {
    setOptions((prev) =>
      prev.map((opt, idx) =>
        idx === index ? { ...opt, is_correct: !opt.is_correct } : opt
      )
    );
  };
  const removeOption = (index) => {
    setOptions((prev) => prev.filter((_, idx) => idx !== index));
  };

  const handleFilterChange = (next) => {
    const merged = { ...filters, ...next };
    setFilters(merged);
    loadDashboard(merged);
  };

  const viewSubmission = async (sessionId) => {
    if (!sessionId) return;
    try {
      const data = await apiFetch(`/admin/sessions/${sessionId}/answers`);
      setSubmissionView({
        open: true,
        rows: data,
        reviewed: {}
      });
    } catch (err) {
      setError(err.message);
    }
  };

  const viewViolations = async (sessionId) => {
    if (!sessionId) return;
    try {
      const data = await apiFetch(`/admin/sessions/${sessionId}/violations`);
      alert(JSON.stringify(data, null, 2));
    } catch (err) {
      setError(err.message);
    }
  };

  const setUserActive = async (userId, isActive) => {
    try {
      await apiFetch(`/admin/users/${userId}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: isActive })
      });
      setSuccessMessage(
        isActive ? "User re-enabled successfully." : "User disabled successfully."
      );
      await loadData();
      await loadDashboard();
    } catch (err) {
      setError(err.message);
    }
  };

  const generateTempPassword = () =>
    Math.random().toString(36).slice(2, 8) + Math.random().toString(36).slice(2, 6);

  const resetPassword = async (userId, username) => {
    const newPassword = generateTempPassword();
    try {
      await apiFetch(`/admin/users/${userId}`, {
        method: "PATCH",
        body: JSON.stringify({ password: newPassword })
      });
      setSuccessMessage(
        `Temporary password for ${username}: ${newPassword}`
      );
    } catch (err) {
      setError(err.message);
    }
  };

  const handleConfirmAction = async () => {
    if (!actionModal.user) return;
    setError("");
    setSuccessMessage("");
    const { user, type } = actionModal;
    if (type === "disable") {
      await setUserActive(user.id, false);
    } else if (type === "enable") {
      await setUserActive(user.id, true);
    } else if (type === "reset") {
      await resetPassword(user.id, user.username);
    }
    setActionModal({ open: false, type: "", user: null });
  };

  const assignTestToUser = async (userId) => {
    const setId = assignedSetByUser[userId];
    if (!setId) {
      setError("Select a question set first.");
      return;
    }
    try {
      await apiFetch("/admin/assignments", {
        method: "POST",
        body: JSON.stringify({
          question_set_id: Number(setId),
          user_id: Number(userId)
        })
      });
      await loadData();
      await loadDashboard();
    } catch (err) {
      setError(err.message);
    }
  };

  const generateSessionCode = async (assignmentId) => {
    try {
      await apiFetch(`/admin/assignments/${assignmentId}/session-code`, {
        method: "POST"
      });
      await loadData();
      await loadDashboard();
    } catch (err) {
      setError(err.message);
    }
  };

  const copySessionCode = async (code) => {
    if (!code) return;
    try {
      await navigator.clipboard.writeText(code);
      setToastMessage("Copied to clipboard");
      setTimeout(() => setToastMessage(""), 3500);
    } catch (err) {
      setError("Unable to copy session code.");
    }
  };

  const adminTabs = [
    { id: "summary", label: "Summary" },
    { id: "users", label: "Users" },
    { id: "tests", label: "Tests" },
    { id: "question_sets", label: "Question Sets" },
    { id: "violations", label: "Violations" },
    { id: "settings", label: "Settings" }
  ];

  return (
    <div className="page">
      <header className="header">
        <div>
          <h1>Admin Console</h1>
          <p className="subtle">Summary dashboard and content management</p>
        </div>
        <button onClick={onLogout}>Logout</button>
      </header>
      {error && <div className="error">{error}</div>}

      <nav className="tabs">
        {adminTabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`tab ${activeTab === tab.id ? "active" : ""}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {activeTab === "summary" && (
        <section className="card">
          <h2>Dashboard</h2>
          <div className="filters">
            <select
              value={filters.testType}
              onChange={(e) => handleFilterChange({ testType: e.target.value })}
            >
              <option value="">All Types</option>
              {testTypes.map((type) => (
                <option key={type.id} value={type.name}>
                  {type.name}
                </option>
              ))}
            </select>
            <select
              value={filters.status}
              onChange={(e) => handleFilterChange({ status: e.target.value })}
            >
              <option value="">All Statuses</option>
              <option value="Not Started">Not Started</option>
              <option value="In Progress">In Progress</option>
              <option value="Submitted">Submitted</option>
              <option value="Auto-Submitted">Auto-Submitted</option>
              <option value="Expired">Expired</option>
            </select>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={filters.violationsOnly}
                onChange={(e) =>
                  handleFilterChange({ violationsOnly: e.target.checked })
                }
              />
              Violations only
            </label>
          </div>
          <div className="table summary-table">
            <div className="table-header">
              <span>User</span>
              <span>Total Tests</span>
              <span>Status</span>
              <span>Violations</span>
              <span>Actions</span>
            </div>
            {dashboardRows.map((candidate) => {
              const isExpanded = summaryExpanded[candidate.user_id];
              const tests = candidate.tests || [];
              const showChildren = Boolean(isExpanded);
              return (
                <div key={`summary-${candidate.user_id}`}>
                  <div className="table-row summary-parent">
                    <span className="summary-user">
                      <button
                        className="summary-toggle"
                        onClick={() =>
                          setSummaryExpanded((prev) => ({
                            ...prev,
                            [candidate.user_id]: !prev[candidate.user_id]
                          }))
                        }
                        aria-expanded={Boolean(isExpanded)}
                        aria-label={
                          isExpanded ? "Collapse user tests" : "Expand user tests"
                        }
                      >
                        {isExpanded ? "−" : "+"}
                      </button>
                      <span>{candidate.username}</span>
                    </span>
                    <span>{candidate.total_tests_assigned}</span>
                    <span>{candidate.overall_status}</span>
                    <span>{candidate.total_violations}</span>
                    <span className="actions summary-actions">
                      <button
                        className="ghost"
                        onClick={() => disableUser(candidate.user_id)}
                        disabled={!candidate.is_active}
                      >
                        Disable user
                      </button>
                      <button
                        className="ghost"
                        onClick={() => resetPassword(candidate.user_id)}
                      >
                        Reset password
                      </button>
                    </span>
                  </div>
                  {tests.length > 0 && (
                    <div
                      className={`history-row summary-children ${
                        showChildren ? "expanded" : "collapsed"
                      }`}
                    >
                      <div className="table subtable summary-test-table">
                        <div className="table-header">
                          <span>Test Name</span>
                          <span>Question Set</span>
                          <span>Type</span>
                          <span>Status</span>
                          <span>Time</span>
                          <span>Violations</span>
                          <span>Actions</span>
                        </div>
                        {showChildren &&
                          tests.map((test) => {
                          const historyKey = `${candidate.user_id}-${test.assignment_id}`;
                          const showHistory =
                            (test.history || []).length > 1 &&
                            summaryHistoryExpanded[historyKey];
                          return (
                            <div key={test.assignment_id}>
                              <div className="table-row summary-child">
                                <span>{test.test_name || "-"}</span>
                                <span>{test.question_set || "-"}</span>
                                <span>{test.test_type}</span>
                                <span>{test.status}</span>
                                <span>
                                  {test.status === "In Progress" &&
                                  test.time_remaining_seconds !== null
                                    ? `${Math.ceil(
                                        test.time_remaining_seconds / 60
                                      )}m left`
                                    : test.time_taken_seconds
                                    ? `${Math.ceil(test.time_taken_seconds / 60)}m`
                                    : "-"}
                                </span>
                                <span>{test.violations}</span>
                                <span className="actions summary-actions">
                                  <button
                                    className="ghost"
                                    onClick={() => viewSubmission(test.session_id)}
                                    disabled={!test.session_id}
                                  >
                                    View submission
                                  </button>
                                  <button
                                    className="ghost"
                                    onClick={() => viewViolations(test.session_id)}
                                    disabled={!test.session_id}
                                  >
                                    View violations
                                  </button>
                                  {(test.history || []).length > 1 && (
                                    <button
                                      className="ghost"
                                      onClick={() =>
                                        setSummaryHistoryExpanded((prev) => ({
                                          ...prev,
                                          [historyKey]: !prev[historyKey]
                                        }))
                                      }
                                    >
                                      {showHistory ? "Hide history" : "Show history"}
                                    </button>
                                  )}
                                </span>
                              </div>
                              {showHistory && (
                                <div className="history-row">
                                  <div className="table subtable summary-history-table">
                                    <div className="table-header">
                                      <span>Attempt</span>
                                      <span>Status</span>
                                      <span>Time</span>
                                      <span>Violations</span>
                                      <span>Actions</span>
                                    </div>
                                    {(test.history || [])
                                      .slice(1)
                                      .map((attempt) => (
                                        <div
                                          className="table-row summary-child"
                                          key={attempt.session_id}
                                        >
                                          <span>Attempt {attempt.attempt}</span>
                                          <span>{attempt.status}</span>
                                          <span>
                                            {attempt.time_taken_seconds
                                              ? `${Math.ceil(
                                                  attempt.time_taken_seconds / 60
                                                )}m`
                                              : "-"}
                                          </span>
                                          <span>{attempt.violation_count}</span>
                                          <span className="actions summary-actions">
                                            <button
                                              className="ghost"
                                              onClick={() =>
                                                viewSubmission(attempt.session_id)
                                              }
                                              disabled={!attempt.session_id}
                                            >
                                              View submission
                                            </button>
                                            <button
                                              className="ghost"
                                              onClick={() =>
                                                viewViolations(attempt.session_id)
                                              }
                                              disabled={!attempt.session_id}
                                            >
                                              View violations
                                            </button>
                                          </span>
                                        </div>
                                      ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          );
                          })}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      )}

      {submissionView.open && (
        <div className="modal-overlay">
          <div className="modal-content">
            <header className="header">
              <h2>Submission Review</h2>
              <button
                className="ghost"
                onClick={() =>
                  setSubmissionView({ open: false, rows: [], reviewed: {} })
                }
              >
                Close
              </button>
            </header>
            <div className="qa-grid">
              <div className="qa-header">Question</div>
              <div className="qa-header">Answer</div>
              {submissionView.rows.map((row) => (
                <React.Fragment key={row.question_id}>
                  <div className="qa-cell">
                    <strong>{row.question_title}</strong>
                    <div className="subtle">{row.answer_type}</div>
                  </div>
                  <div className="qa-cell">
                    {row.answer_type === "multiple_choice" ? (
                      <ul className="answer-list">
                        {row.options.map((option) => {
                          const selected = row.selected_option_ids.includes(
                            option.id
                          );
                          return (
                            <li key={option.id}>
                              <input
                                type="checkbox"
                                checked={selected}
                                readOnly
                              />
                              <span>{option.option_text}</span>
                            </li>
                          );
                        })}
                      </ul>
                    ) : (
                      <pre className="answer-text">{row.answer_text || "-"}</pre>
                    )}
                    <label className="checkbox">
                      <input
                        type="checkbox"
                        checked={Boolean(
                          submissionView.reviewed[row.question_id]
                        )}
                        onChange={(e) =>
                          setSubmissionView((prev) => ({
                            ...prev,
                            reviewed: {
                              ...prev.reviewed,
                              [row.question_id]: e.target.checked
                            }
                          }))
                        }
                      />
                      Reviewed
                    </label>
                  </div>
                </React.Fragment>
              ))}
            </div>
          </div>
        </div>
      )}

      {activeTab === "users" && (
        <section className="card">
          <h2>User Management</h2>
          <div className="create-user-panel">
            <button
              className="ghost"
              onClick={() => setCreateUserOpen((prev) => !prev)}
              aria-expanded={createUserOpen}
              aria-label={createUserOpen ? "Collapse create user" : "Expand create user"}
            >
              {createUserOpen ? "−" : "+"} Add user
            </button>
            {createUserOpen && (
              <div className="create-user-body">
                <div className="create-user-header">Create New User</div>
                <form onSubmit={handleCreateUser}>
                  <input
                    placeholder="Username"
                    value={newUser.username}
                    onChange={(e) =>
                      setNewUser({ ...newUser, username: e.target.value })
                    }
                  />
                  <input
                    placeholder="Password"
                    type="password"
                    value={newUser.password}
                    onChange={(e) =>
                      setNewUser({ ...newUser, password: e.target.value })
                    }
                  />
                  <select
                    value={newUser.role}
                    onChange={(e) =>
                      setNewUser({ ...newUser, role: e.target.value })
                    }
                  >
                    <option value="candidate">Candidate</option>
                    <option value="admin">Admin</option>
                  </select>
                  <button type="submit">Create User</button>
                </form>
              </div>
            )}
          </div>
          <div className="split-form users-section">
            <h3>Users</h3>
            {successMessage && <div className="success">{successMessage}</div>}
            <div className="table user-table">
              <div className="table-header">
                <span>User</span>
                <span title="Derived from all tests assigned to this user">
                  Overall Status
                </span>
                <span>Actions</span>
              </div>
              {users
                .filter((user) => user.role === "candidate")
                .map((user) => {
                  const candidate = dashboardRows.find(
                    (row) => row.user_id === user.id
                  );
                  const tests = (candidate?.tests || []).slice().sort(
                    (a, b) => b.assignment_id - a.assignment_id
                  );
                  const hasTests = tests.length > 0;
                  const hasInProgress = tests.some(
                    (test) => test.status === "In Progress"
                  );
                  const allSubmitted = hasTests
                    ? tests.every((test) => test.status === "Submitted")
                    : false;
                  const allNotStarted = hasTests
                    ? tests.every((test) => test.status === "Not Started")
                    : false;
                  const overallStatus = allSubmitted
                    ? "Submitted"
                    : hasInProgress
                    ? "In Progress"
                    : allNotStarted
                    ? "Not Started"
                    : hasTests
                    ? "Mixed"
                    : "Unassigned";
                  const displayStatus = user.is_active
                    ? overallStatus
                    : "Disabled";
                  return (
                    <div key={`user-${user.id}`}>
                      <div
                        className={`table-row ${
                          user.is_active ? "" : "is-disabled"
                        }`}
                      >
                        <span className="user-name">{user.username}</span>
                        <span>{displayStatus}</span>
                        <span className="actions">
                          <button
                            className="ghost"
                            onClick={() =>
                              setUserManageOpenId((prev) =>
                                prev === user.id ? null : user.id
                              )
                            }
                          >
                            Manage Tests
                          </button>
                          <button
                            className="ghost"
                            onClick={() =>
                              setActionModal({
                                open: true,
                                type: user.is_active ? "disable" : "enable",
                                user
                              })
                            }
                          >
                            {user.is_active ? "Disable user" : "Re-enable user"}
                          </button>
                          <button
                            className="ghost"
                            onClick={() =>
                              setActionModal({ open: true, type: "reset", user })
                            }
                          >
                            Reset password
                          </button>
                        </span>
                      </div>
                      {userManageOpenId === user.id && (
                        <div className="history-row">
                          <div className="manage-panel">
                            <div className="manage-panel-header">
                              Manage Tests for {user.username}
                            </div>
                            <div className="manage-panel-helper">
                              Assign a new test to this user
                            </div>
                            <div className="manage-panel-controls">
                              <select
                                value={assignedSetByUser[user.id] || ""}
                                onChange={(e) =>
                                  setAssignedSetByUser((prev) => ({
                                    ...prev,
                                    [user.id]: e.target.value
                                  }))
                                }
                              >
                                <option value="">Select question set</option>
                                {questionSets.map((set) => (
                                  <option key={set.id} value={set.id}>
                                    {set.name}
                                  </option>
                                ))}
                              </select>
                              <button
                                className="ghost secondary"
                                onClick={() => assignTestToUser(user.id)}
                              >
                                {tests.length > 0 ? "Assign / Update" : "Assign"}
                              </button>
                            </div>
                            <div className="manage-panel-actions">
                              <button
                                className="ghost secondary"
                                onClick={() => {
                                  const latest = tests[0];
                                  if (latest) {
                                    generateSessionCode(latest.assignment_id);
                                  }
                                }}
                                disabled={tests.length === 0}
                              >
                                + Create New Test Attempt
                              </button>
                            </div>
                            <div className="table manage-tests-table">
                              <div className="table-header">
                                <span>Question Set</span>
                                <span>Type</span>
                                <span>Status</span>
                                <span>Session Code</span>
                                <span>Actions</span>
                              </div>
                              {tests.length === 0 && (
                                <div className="table-row">
                                  <span className="subtle">No tests assigned.</span>
                                </div>
                              )}
                              {tests.map((test) => (
                                <div
                                  className="table-row"
                                  key={`manage-${test.assignment_id}`}
                                >
                                  <span>{test.question_set || "-"}</span>
                                  <span>{test.test_type}</span>
                                  <span>{test.status}</span>
                                  <span className="monospace">
                                    {test.session_code || "-"}
                                  </span>
                                  <span className="actions utility-actions">
                                    {test.session_code && (
                                      <button
                                        className="ghost utility"
                                        onClick={() =>
                                          copySessionCode(test.session_code)
                                        }
                                        disabled={test.status !== "Not Started"}
                                        title={
                                          test.status === "Not Started"
                                            ? ""
                                            : "Session code is read-only for completed tests"
                                        }
                                      >
                                        Copy code
                                      </button>
                                    )}
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
            </div>
          </div>
        </section>
      )}

      {activeTab === "tests" && (
        <section className="card">
          <h2>Test Setup</h2>
          <section className="split-form">
            <h3>Create Test</h3>
            <form onSubmit={handleCreateTest}>
              <label>
                Test title
                <input
                  placeholder="Test title"
                  value={newTest.title}
                  onChange={(e) =>
                    setNewTest({ ...newTest, title: e.target.value })
                  }
                />
              </label>
              <label>
                Test type
                <select
                  value={newTest.test_type_id}
                  onChange={(e) =>
                    setNewTest({ ...newTest, test_type_id: e.target.value })
                  }
                >
                  <option value="">Select test type</option>
                  {testTypes.map((type) => (
                    <option key={type.id} value={type.id}>
                      {type.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Question set
                <select
                  value={newTest.question_set_id}
                  onChange={(e) =>
                    setNewTest({ ...newTest, question_set_id: e.target.value })
                  }
                >
                  <option value="">Select question set</option>
                  {questionSets.map((set) => (
                    <option key={set.id} value={set.id}>
                      {set.name}
                    </option>
                  ))}
                </select>
              </label>
              <div className="row">
                <label>
                  Duration (minutes)
                  <input
                    type="number"
                    value={newTest.duration_minutes}
                    onChange={(e) =>
                      setNewTest({ ...newTest, duration_minutes: e.target.value })
                    }
                  />
                </label>
                <label>
                  Warning before end (minutes)
                  <input
                    type="number"
                    value={newTest.warning_minutes}
                    onChange={(e) =>
                      setNewTest({ ...newTest, warning_minutes: e.target.value })
                    }
                  />
                  <span className="subtle">
                    Candidates will be warned {newTest.warning_minutes} minutes
                    before timeout.
                  </span>
                </label>
              </div>
              <button type="submit">Create Test</button>
            </form>
          </section>
          <section className="split-form">
            <button
              className="ghost"
              onClick={() => setTestTypesOpen((prev) => !prev)}
              aria-expanded={testTypesOpen}
              aria-label={testTypesOpen ? "Collapse test types" : "Expand test types"}
            >
              {testTypesOpen ? "−" : "+"} Manage Test Types
            </button>
            {testTypesOpen && (
              <div className="test-types-panel">
                <form onSubmit={handleCreateTestType}>
                  <label>
                    Type name
                    <input
                      placeholder="Type name (e.g., QA, Java)"
                      value={newTestType.name}
                      onChange={(e) => setNewTestType({ name: e.target.value })}
                    />
                  </label>
                  <button className="secondary" type="submit">
                    Add Type
                  </button>
                </form>
                <div className="type-list">
                  {testTypes.map((type) => (
                    <div key={type.id} className="type-pill">
                      {type.name}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </section>
          <section className="split-form">
            <h3>Existing Tests</h3>
            <div className="table tests-table">
              <div className="table-header">
                <span>Title</span>
                <span>Type</span>
                <span>Question Set</span>
                <span>Duration</span>
                <span>Warning</span>
                <span>Status</span>
                <span>Actions</span>
              </div>
              {tests.map((test) => (
                <div className="table-row" key={test.id}>
                  <span>{test.title}</span>
                  <span>{test.test_type || "-"}</span>
                  <span>{test.question_set_name || "-"}</span>
                  <span>{test.duration_minutes}m</span>
                  <span>{test.warning_minutes}m</span>
                  <span>{test.is_active ? "Active" : "Disabled"}</span>
                  <span className="actions utility-actions">
                    <button
                      className="ghost secondary"
                      onClick={() => toggleTestActive(test.id, !test.is_active)}
                    >
                      {test.is_active ? "Disable" : "Re-enable"}
                    </button>
                  </span>
                </div>
              ))}
            </div>
          </section>
        </section>
      )}

      {actionModal.open && (
        <div className="modal-overlay">
          <div className="modal-content">
            <header className="header">
              <h2>
                {actionModal.type === "reset"
                  ? "Reset Password"
                  : actionModal.type === "disable"
                  ? "Disable User"
                  : "Re-enable User"}
              </h2>
            </header>
            <p>
              {actionModal.type === "reset"
                ? `Reset password for ${actionModal.user?.username}? This will invalidate the current password.`
                : actionModal.type === "disable"
                ? `Disable ${actionModal.user?.username}? This will prevent login until re-enabled.`
                : `Re-enable ${actionModal.user?.username}?`}
            </p>
            <div className="actions">
              <button onClick={handleConfirmAction}>Confirm</button>
              <button
                className="ghost"
                onClick={() =>
                  setActionModal({ open: false, type: "", user: null })
                }
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {toastMessage && <div className="toast">{toastMessage}</div>}

      {activeTab === "question_sets" && (
        <section className="card">
          <h2>Question Sets</h2>
          <div className="split-form">
            <button
              className="ghost"
              onClick={() => setCreateQuestionSetOpen((prev) => !prev)}
              aria-expanded={createQuestionSetOpen}
              aria-label={
                createQuestionSetOpen
                  ? "Collapse create question set"
                  : "Expand create question set"
              }
            >
              {createQuestionSetOpen ? "−" : "+"} Create New Question Set
            </button>
            {createQuestionSetOpen && (
              <div className="question-set-panel">
                <form onSubmit={handleCreateQuestionSet}>
                  <label>
                    Set name
                    <input
                      placeholder="Set name"
                      value={newQuestionSet.name}
                      onChange={(e) =>
                        setNewQuestionSet({
                          ...newQuestionSet,
                          name: e.target.value
                        })
                      }
                    />
                  </label>
                  <label>
                    Test type
                    <select
                      value={newQuestionSet.test_type_id}
                      onChange={(e) =>
                        setNewQuestionSet({
                          ...newQuestionSet,
                          test_type_id: e.target.value
                        })
                      }
                    >
                      <option value="">Select test type</option>
                      {testTypes.map((type) => (
                        <option key={type.id} value={type.id}>
                          {type.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Description (optional)
                    <textarea
                      placeholder="Description (optional)"
                      value={newQuestionSet.description}
                      onChange={(e) =>
                        setNewQuestionSet({
                          ...newQuestionSet,
                          description: e.target.value
                        })
                      }
                    />
                  </label>
                  <div className="row">
                    <label>
                      Default Duration (optional)
                      <input
                        type="number"
                        value={newQuestionSet.duration_minutes}
                        onChange={(e) =>
                          setNewQuestionSet({
                            ...newQuestionSet,
                            duration_minutes: e.target.value
                          })
                        }
                      />
                    </label>
                    <label>
                      Default Warning (optional)
                      <input
                        type="number"
                        value={newQuestionSet.warning_minutes}
                        onChange={(e) =>
                          setNewQuestionSet({
                            ...newQuestionSet,
                            warning_minutes: e.target.value
                          })
                        }
                      />
                      <span className="subtle">
                        Actual timing is configured per Test.
                      </span>
                    </label>
                  </div>
                  <button type="submit">Create Set</button>
                </form>
              </div>
            )}
          </div>

          <div className="split-form">
            <h3>Select Question Set to Edit</h3>
            <select
              value={activeQuestionSetId}
              onChange={(e) => {
                const value = e.target.value;
                setActiveQuestionSetId(value);
                setEditingQuestion(null);
                setQuestionEditorOpen(false);
                loadQuestionSetQuestions(value);
                const selected = questionSets.find(
                  (set) => set.id === Number(value)
                );
                setEditQuestionSet(
                  selected
                    ? {
                        ...selected,
                        duration_minutes: selected.duration_minutes || 60,
                        warning_minutes: selected.warning_minutes || 5
                      }
                    : null
                );
              }}
            >
              <option value="">Select a set</option>
              {questionSets.map((set) => (
                <option key={set.id} value={set.id}>
                  {set.name}
                </option>
              ))}
            </select>
          </div>

          {activeQuestionSetId && (
            <>
              <h3 className="question-edit-header">
                Editing Question Set:{" "}
                {questionSets.find((set) => set.id === Number(activeQuestionSetId))
                  ?.name || "Unknown"}
              </h3>
              {editQuestionSet && (
                <form onSubmit={handleUpdateQuestionSet} className="split-form">
                  <h3>Edit Set Details</h3>
                  <label>
                    Set name
                    <input
                      placeholder="Set name"
                      value={editQuestionSet.name}
                      onChange={(e) =>
                        setEditQuestionSet({
                          ...editQuestionSet,
                          name: e.target.value
                        })
                      }
                    />
                  </label>
                  <label>
                    Test type
                    <select
                      value={editQuestionSet.test_type_id}
                      onChange={(e) =>
                        setEditQuestionSet({
                          ...editQuestionSet,
                          test_type_id: e.target.value
                        })
                      }
                    >
                      <option value="">Select test type</option>
                      {testTypes.map((type) => (
                        <option key={type.id} value={type.id}>
                          {type.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Description
                    <textarea
                      placeholder="Description"
                      value={editQuestionSet.description || ""}
                      onChange={(e) =>
                        setEditQuestionSet({
                          ...editQuestionSet,
                          description: e.target.value
                        })
                      }
                    />
                  </label>
                  <div className="row">
                    <label>
                      Default Duration (optional)
                      <input
                        type="number"
                        value={editQuestionSet.duration_minutes}
                        onChange={(e) =>
                          setEditQuestionSet({
                            ...editQuestionSet,
                            duration_minutes: e.target.value
                          })
                        }
                      />
                    </label>
                    <label>
                      Default Warning (optional)
                      <input
                        type="number"
                        value={editQuestionSet.warning_minutes}
                        onChange={(e) =>
                          setEditQuestionSet({
                            ...editQuestionSet,
                            warning_minutes: e.target.value
                          })
                        }
                      />
                      <span className="subtle">
                        Actual timing is configured per Test.
                      </span>
                    </label>
                  </div>
                  <button type="submit">Update Set</button>
                </form>
              )}
              <section className="question-management">
                <div className="question-management-header">
                  <h3>Question Management</h3>
                  <button
                    type="button"
                    onClick={() => {
                      setEditingQuestion(null);
                      setQuestionEditorOpen(true);
                      setNewQuestion({ title: "", body: "", sections: "" });
                      setAnswerType("long_text");
                      setAllowMultiple(false);
                      setOptions([{ option_text: "", is_correct: false }]);
                    }}
                  >
                    + Add Question
                  </button>
                </div>
                <div className="table question-table">
                  <div className="table-header">
                    <span>Question</span>
                    <span>Type</span>
                    <span>Actions</span>
                  </div>
                  {questionSetQuestions.map((question, index) => (
                    <div
                      key={question.id}
                      className="table-row"
                      draggable
                      onDragStart={handleQuestionSetDragStart(index)}
                      onDragOver={(event) => event.preventDefault()}
                      onDrop={handleQuestionSetDrop(index)}
                    >
                      <span className="question-snippet">
                        {index + 1}.{" "}
                        {(question.body || question.title || "").slice(0, 80)}
                      </span>
                      <span>
                        {question.answer_type === "multiple_choice"
                          ? "MCQ"
                          : "Text"}
                      </span>
                      <span className="actions">
                        <button
                          type="button"
                          className="ghost"
                          onClick={() => handleQuestionSelect(question)}
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          className="ghost"
                          onClick={() => handleQuestionDelete(question.id)}
                        >
                          Remove
                        </button>
                      </span>
                    </div>
                  ))}
                </div>
                <button type="button" onClick={handleQuestionSetOrderSave}>
                  Save order
                </button>
                {(questionEditorOpen || editingQuestion) && (
                  <form onSubmit={handleCreateQuestion} className="split-form">
                    <h3>{editingQuestion ? "Edit Question" : "Add Question"}</h3>
                <input
                  placeholder="Question title"
                  value={newQuestion.title}
                  onChange={(e) =>
                    setNewQuestion({ ...newQuestion, title: e.target.value })
                  }
                />
                <textarea
                  placeholder="Question prompt (Markdown supported)"
                  value={newQuestion.body}
                  onChange={(e) =>
                    setNewQuestion({ ...newQuestion, body: e.target.value })
                  }
                />
                <textarea
                  placeholder="Sections / case context (optional)"
                  value={newQuestion.sections}
                  onChange={(e) =>
                    setNewQuestion({ ...newQuestion, sections: e.target.value })
                  }
                />
                <div className="row">
                  <label>
                    Answer type
                    <select
                      value={answerType}
                      onChange={(e) => setAnswerType(e.target.value)}
                    >
                      <option value="long_text">Long text</option>
                      <option value="short_text">Short text</option>
                      <option value="multiple_choice">Multiple choice</option>
                    </select>
                  </label>
                  {answerType === "multiple_choice" && (
                    <label className="checkbox">
                      <input
                        type="checkbox"
                        checked={allowMultiple}
                        onChange={(e) => setAllowMultiple(e.target.checked)}
                      />
                      Allow multiple correct
                    </label>
                  )}
                </div>
                {answerType === "multiple_choice" && (
                  <div className="option-list">
                    {options.map((option, index) => (
                      <div key={index} className="option-item">
                        <input
                          placeholder={`Option ${index + 1}`}
                          value={option.option_text}
                          onChange={(e) => updateOption(index, e.target.value)}
                        />
                        <label className="checkbox">
                          <input
                            type="checkbox"
                            checked={option.is_correct}
                            onChange={() => toggleCorrect(index)}
                          />
                          Correct
                        </label>
                        <button
                          type="button"
                          className="ghost"
                          onClick={() => removeOption(index)}
                          disabled={options.length <= 1}
                        >
                          Remove
                        </button>
                      </div>
                    ))}
                    <button type="button" className="ghost" onClick={addOption}>
                      Add option
                    </button>
                  </div>
                )}
                <div className="actions">
                  <button type="submit">
                    {editingQuestion ? "Save changes" : "Add question"}
                  </button>
                  {editingQuestion && (
                    <button
                      type="button"
                      className="ghost"
                      onClick={() => {
                        setEditingQuestion(null);
                        setQuestionEditorOpen(false);
                        setNewQuestion({ title: "", body: "", sections: "" });
                        setAnswerType("long_text");
                        setAllowMultiple(false);
                        setOptions([{ option_text: "", is_correct: false }]);
                      }}
                    >
                      Cancel
                    </button>
                  )}
                </div>
                  </form>
                )}
              </section>
            </>
          )}
        </section>
      )}

      {activeTab === "violations" && (
        <section className="card">
          <h2>Violations Feed</h2>
          <pre>
            {monitoring ? JSON.stringify(monitoring, null, 2) : "Loading..."}
          </pre>
        </section>
      )}

      {activeTab === "settings" && (
        <section className="card">
          <h2>Settings</h2>
          <p className="subtle">Configure additional admin settings here.</p>
        </section>
      )}
    </div>
  );
}

function useExamSecurity({ sessionId, token, onViolation }) {
  const lastViolationRef = useRef(0);
  const modalRef = useRef(null);

  const logViolation = (eventType, metadata = "") => {
    const now = Date.now();
    if (now - lastViolationRef.current < 2000) {
      return;
    }
    lastViolationRef.current = now;
    onViolation(eventType, metadata);
    modalRef.current?.showModal();
  };

  useEffect(() => {
    const handleFullscreen = () => {
      if (!document.fullscreenElement) {
        logViolation("fullscreen_exit", "User exited fullscreen");
      }
    };
    const handleVisibility = () => {
      if (document.hidden) {
        logViolation("tab_switch", "Document hidden");
      }
    };
    const handleBlur = () => {
      logViolation("window_blur", "Window lost focus");
    };
    const handleKeydown = (event) => {
      if (
        event.key === "F12" ||
        (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === "i")
      ) {
        logViolation("devtools_open", "Devtools key combo");
      }
    };

    const devtoolsInterval = setInterval(() => {
      const widthDiff = window.outerWidth - window.innerWidth;
      const heightDiff = window.outerHeight - window.innerHeight;
      if (widthDiff > 160 || heightDiff > 160) {
        logViolation("devtools_open", "Devtools size heuristic");
      }
    }, 3000);

    document.addEventListener("fullscreenchange", handleFullscreen);
    document.addEventListener("visibilitychange", handleVisibility);
    window.addEventListener("blur", handleBlur);
    window.addEventListener("keydown", handleKeydown);

    return () => {
      clearInterval(devtoolsInterval);
      document.removeEventListener("fullscreenchange", handleFullscreen);
      document.removeEventListener("visibilitychange", handleVisibility);
      window.removeEventListener("blur", handleBlur);
      window.removeEventListener("keydown", handleKeydown);
    };
  }, [sessionId, token]);

  return modalRef;
}

function CandidateDashboard({ onLogout }) {
  const [sessionCodeInput, setSessionCodeInput] = useState("");
  const [error, setError] = useState("");
  const [isValidating, setIsValidating] = useState(false);
  const [darkMode, setDarkMode] = useState(
    localStorage.getItem("candidate_theme") === "dark"
  );
  const navigate = useNavigate();

  useEffect(() => {
    const notice = sessionStorage.getItem("candidate_notice");
    if (notice) {
      setError(notice);
      sessionStorage.removeItem("candidate_notice");
    }
  }, []);

  useEffect(() => {
    localStorage.setItem("candidate_theme", darkMode ? "dark" : "light");
    document.body.classList.toggle("candidate-dark", darkMode);
    return () => document.body.classList.remove("candidate-dark");
  }, [darkMode]);

  const startTest = async () => {
    const code = sessionCodeInput.trim();
    if (!code) {
      setError("Enter the session code provided by the admin.");
      return;
    }
    setError("");
    setIsValidating(true);
    try {
      const validation = await apiFetch("/sessions/validate", {
        method: "POST",
        body: JSON.stringify({ session_code: code })
      });
      if (!validation.valid) {
        const reason = validation.reason || "invalid";
        const message =
          reason === "wrong_user"
            ? "Session code does not belong to this user."
            : reason === "in_progress"
            ? "This test is already in progress and cannot be restarted."
            : reason === "used"
            ? "This session code has already been used."
            : reason === "inactive"
            ? "This session code is inactive."
            : "Invalid session code.";
        setError(message);
        setIsValidating(false);
        return;
      }
      const session = await apiFetch("/candidate/sessions/start", {
        method: "POST",
        body: JSON.stringify({ session_code: code })
      });
      localStorage.setItem("active_session", JSON.stringify(session));
      sessionStorage.setItem("allow_session_entry", "1");
      navigate("/candidate/session");
    } catch (err) {
      setError(err.message);
      setIsValidating(false);
    }
  };

  return (
    <div className="page candidate-entry-page">
      <div className="entry-topbar">
        <label className="entry-toggle">
          <input
            type="checkbox"
            checked={darkMode}
            onChange={(e) => setDarkMode(e.target.checked)}
          />
          Dark mode
        </label>
        <button className="ghost" onClick={onLogout}>
          Logout
        </button>
      </div>
      <section className="card entry-card">
        <h1>Enter Session Code</h1>
        <p className="subtle">
          Enter the session code provided by your administrator to begin your test.
        </p>
        <div className="entry-actions">
          <input
            className="monospace entry-input"
            placeholder="e.g. ABCD-1234"
            value={sessionCodeInput}
            onChange={(e) => setSessionCodeInput(e.target.value)}
          />
          <button
            className="entry-button"
            onClick={startTest}
            disabled={!sessionCodeInput.trim() || isValidating}
          >
            {isValidating ? "Validating…" : "Start Test"}
          </button>
        </div>
        {error && <div className="error entry-error">{error}</div>}
      </section>
    </div>
  );
}

function CandidateSession() {
  const navigate = useNavigate();
  const [session, setSession] = useState(null);
  const [answerText, setAnswerText] = useState({});
  const [selectedOptions, setSelectedOptions] = useState({});
  const [error, setError] = useState("");
  const [warning, setWarning] = useState(false);
  const [expired, setExpired] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [submitMessage, setSubmitMessage] = useState("");
  const [submitInfo, setSubmitInfo] = useState(null);
  const [saveState, setSaveState] = useState("idle");
  const [saveError, setSaveError] = useState("");
  const [candidateToast, setCandidateToast] = useState("");
  const [showSubmitConfirm, setShowSubmitConfirm] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(
    Boolean(document.fullscreenElement)
  );
  const [activeQuestionIndex, setActiveQuestionIndex] = useState(0);
  const [activeTab, setActiveTab] = useState("instructions");
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const stored = localStorage.getItem("active_session");
    const allowEntry = sessionStorage.getItem("allow_session_entry");
    if (!stored) {
      navigate("/candidate");
      return;
    }
    if (!allowEntry) {
      localStorage.removeItem("active_session");
      sessionStorage.setItem(
        "candidate_notice",
        "Test access is not allowed after exit."
      );
      navigate("/candidate");
      return;
    }
    sessionStorage.removeItem("allow_session_entry");
    setSession(JSON.parse(stored));
  }, []);

  useEffect(() => {
    const darkMode = localStorage.getItem("candidate_theme") === "dark";
    document.body.classList.toggle("candidate-dark", darkMode);
    return () => document.body.classList.remove("candidate-dark");
  }, []);

  useEffect(() => {
    const handleKeydown = (event) => {
      if (event.ctrlKey && event.key.toLowerCase() === "tab") {
        event.preventDefault();
        const tabs = ["instructions", ...session.questions.map((q) => q.id)];
        const currentIndex = tabs.indexOf(activeTab);
        const nextIndex = (currentIndex + 1) % tabs.length;
        const nextTab = tabs[nextIndex];
        if (nextTab === "instructions") {
          setActiveTab("instructions");
        } else {
          const idx = session.questions.findIndex((q) => q.id === nextTab);
          if (idx >= 0) {
            setActiveQuestionIndex(idx);
            setActiveTab(nextTab);
          }
        }
      }
    };
    if (session) {
      window.addEventListener("keydown", handleKeydown);
    }
    return () => window.removeEventListener("keydown", handleKeydown);
  }, [session, activeTab]);

  useEffect(() => {
    const preventContextMenu = (event) => event.preventDefault();
    const preventNewTab = (event) => {
      if (event.target.tagName === "A" && event.ctrlKey) {
        event.preventDefault();
      }
    };
    document.addEventListener("contextmenu", preventContextMenu);
    document.addEventListener("click", preventNewTab);
    return () => {
      document.removeEventListener("contextmenu", preventContextMenu);
      document.removeEventListener("click", preventNewTab);
    };
  }, []);

  useEffect(() => {
    return () => {
      localStorage.removeItem("active_session");
      sessionStorage.removeItem("allow_session_entry");
    };
  }, []);

  const modalRef = useExamSecurity({
    sessionId: session?.session_id,
    token: session?.violation_token,
    onViolation: async (eventType, metadata) => {
      if (!session) return;
      try {
        await apiFetch("/candidate/violations", {
          method: "POST",
          body: JSON.stringify({
            session_id: session.session_id,
            event_type: eventType,
            metadata,
            token: session.violation_token
          })
        });
      } catch (err) {
        console.error(err);
      }
    }
  });

  const endTime = useMemo(() => {
    if (!session || !session.end_time) return null;
    const value = session.end_time;
    const hasZone = /Z$|[+-]\d{2}:\d{2}$/.test(value);
    return new Date(hasZone ? value : `${value}Z`);
  }, [session]);

  useEffect(() => {
    if (!endTime) return undefined;
    const interval = setInterval(() => {
      setNow(new Date());
    }, 1000);
    return () => clearInterval(interval);
  }, [endTime]);

  const saveAllAnswers = async (isManual = false) => {
    if (!session || submitted || expired) return;
    if (isManual) {
      setSaveError("");
      setCandidateToast("");
      setSaveState("saving");
    }
    try {
      const payloads = session.questions.map((question) => {
        if (question.answer_type === "multiple_choice") {
          return apiFetch("/candidate/answers/save", {
            method: "POST",
            body: JSON.stringify({
              session_id: session.session_id,
              question_id: question.id,
              selected_option_ids: selectedOptions[question.id] || []
            })
          });
        }
        return apiFetch("/candidate/answers/save", {
          method: "POST",
          body: JSON.stringify({
            session_id: session.session_id,
            question_id: question.id,
            answer_text: answerText[question.id] || ""
          })
        });
      });
      await Promise.all(payloads);
      if (isManual) {
        setSaveState("saved");
        setCandidateToast("Answers saved successfully");
        setTimeout(() => setCandidateToast(""), 3500);
        setTimeout(() => setSaveState("idle"), 2500);
      }
    } catch (err) {
      if (isManual) {
        setSaveError("Unable to save answers. Please try again.");
        setCandidateToast("Unable to save answers. Please try again.");
        setTimeout(() => setCandidateToast(""), 3500);
        setSaveState("idle");
      } else {
        setError(err.message);
      }
    }
  };

  const getElapsedSeconds = () => {
    if (!endTime) return null;
    const totalSeconds = Math.max(
      1,
      (session?.test?.duration_minutes || 60) * 60
    );
    const remainingSeconds = Math.max(
      0,
      Math.round((endTime - new Date()) / 1000)
    );
    return Math.max(0, Math.min(totalSeconds, totalSeconds - remainingSeconds));
  };

  const formatDuration = (seconds) => {
    if (seconds === null) return "—";
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, "0")}:${secs
        .toString()
        .padStart(2, "0")}`;
    }
    return `${minutes}:${secs.toString().padStart(2, "0")}`;
  };

  useEffect(() => {
    if (!endTime || !session) return;
    const remainingMs = endTime - now;
    const remainingMinutes = Math.ceil(remainingMs / 60000);
    setWarning(remainingMinutes <= session.test.warning_minutes);
    setExpired(remainingMs <= 0);
  }, [endTime, now, session]);

  useEffect(() => {
    const handler = () => setIsFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener("fullscreenchange", handler);
    return () => document.removeEventListener("fullscreenchange", handler);
  }, []);

  useEffect(() => {
    if (!expired || submitted) return;
    const submit = async () => {
      try {
        await apiFetch("/candidate/submit", {
          method: "POST",
          body: JSON.stringify({ session_id: session.session_id })
        });
        setSubmitted(true);
        setSubmitMessage("Thank you, your answers are submitted.");
        setSubmitInfo({
          title: session?.test?.title || "Test",
          elapsedSeconds: getElapsedSeconds()
        });
      } catch (err) {
        setError(err.message);
      }
    };
    submit();
  }, [expired, submitted, session]);

  useEffect(() => {
    if (!session || submitted) return undefined;
    const interval = setInterval(async () => {
      await saveAllAnswers(false);
    }, 10000);
    return () => clearInterval(interval);
  }, [answerText, selectedOptions, session, submitted, expired]);

  const handleAnswerChange = (questionId, value) => {
    setAnswerText((prev) => ({ ...prev, [questionId]: value }));
  };

  const toggleOption = (questionId, optionId, allowMultiple) => {
    setSelectedOptions((prev) => {
      const current = new Set(prev[questionId] || []);
      if (!allowMultiple) {
        return { ...prev, [questionId]: [optionId] };
      }
      if (current.has(optionId)) {
        current.delete(optionId);
      } else {
        current.add(optionId);
      }
      return { ...prev, [questionId]: Array.from(current) };
    });
  };

  const handleSubmit = async () => {
    try {
      await apiFetch("/candidate/submit", {
        method: "POST",
        body: JSON.stringify({ session_id: session.session_id })
      });
      setSubmitted(true);
      setSubmitMessage("Thank you, your answers are submitted.");
      setSubmitInfo({
        title: session?.test?.title || "Test",
        elapsedSeconds: getElapsedSeconds()
      });
    } catch (err) {
      setError(err.message);
    }
  };

  const handleFinish = () => {
    localStorage.removeItem("active_session");
    navigate("/candidate");
  };

  const requestFullscreen = async () => {
    const root = document.documentElement;
    if (root.requestFullscreen) {
      await root.requestFullscreen();
    }
  };

  if (!session) {
    return null;
  }

  const remainingMs = endTime ? Math.max(0, endTime - now) : 0;
  const remainingMinutes = Math.floor(remainingMs / 60000);
  const remainingSeconds = Math.floor((remainingMs % 60000) / 1000);
  const totalSeconds = Math.max(
    1,
    (session?.test?.duration_minutes || 60) * 60
  );
  const progress = Math.min(100, (remainingMs / (totalSeconds * 1000)) * 100);
  const timerTone =
    progress <= 10 ? "critical" : progress <= 25 ? "warning" : "ok";

  if (submitted) {
    return (
      <div className="page thankyou-page">
        <section className="card thankyou-card">
          <h1>Thank you</h1>
          <p>{submitMessage || "Thank you, your answers are submitted."}</p>
          <p>
            <strong>Test:</strong> {submitInfo?.title || session?.test?.title}
          </p>
          <p>
            <strong>Time taken:</strong>{" "}
            {formatDuration(submitInfo?.elapsedSeconds ?? null)}
          </p>
          <button onClick={handleFinish}>Back to Dashboard</button>
        </section>
      </div>
    );
  }

  return (
    <div className="page">
      <header className="header">
        <h1>{session.test.title}</h1>
        <div>
          Time left: {remainingMinutes}:{remainingSeconds.toString().padStart(2, "0")}
        </div>
        <div className="actions">
          <button
            onClick={() => saveAllAnswers(true)}
            disabled={submitted || expired || saveState === "saving"}
          >
            {saveState === "saving"
              ? "Saving…"
              : saveState === "saved"
              ? "Saved ✓"
              : "Save Answers"}
          </button>
        </div>
      </header>
      {saveError && <div className="error">{saveError}</div>}
      <div className="timer-bar">
        <div
          className={`timer-fill ${timerTone}`}
          style={{ width: `${progress}%` }}
        />
      </div>
      {warning && !expired && (
        <div className="warning">
          {session.test.warning_minutes} minutes remaining. Please review your
          answers.
        </div>
      )}
      {error && <div className="error">{error}</div>}
      {!isFullscreen && (
        <div className="warning">
          Fullscreen mode is required. Please click the button below to
          continue.
        </div>
      )}
      <button onClick={requestFullscreen}>Enter Fullscreen</button>
      {isFullscreen && (
        <>
          <nav className="tabs tabs-scroll">
            <button
              type="button"
              className={`tab ${activeTab === "instructions" ? "active" : ""}`}
              onClick={() => setActiveTab("instructions")}
            >
              Instructions
            </button>
            {session.questions.map((question, index) => (
              <button
                key={question.id}
                type="button"
                className={`tab ${
                  activeTab === question.id ? "active" : ""
                }`}
                onClick={() => {
                  setActiveQuestionIndex(index);
                  setActiveTab(question.id);
                }}
              >
                Question {index + 1}
              </button>
            ))}
          </nav>
          {activeTab === "instructions" && (
            <section className="card">
              <h2>Instructions</h2>
              <p className="subtle">
                Stay in fullscreen mode. Tab switches, blur events, or devtools
                usage are logged. Your work autosaves every few seconds.
              </p>
            </section>
          )}
          {activeTab !== "instructions" && (
            <section className="candidate-layout">
              {(() => {
                const question = session.questions[activeQuestionIndex];
                if (!question) return null;
                return (
                  <>
                    <div className="card">
                      <h2>{question.title}</h2>
                      <div className="question-body">{question.body}</div>
                      {question.sections && (
                        <div className="question-body">{question.sections}</div>
                      )}
                    </div>
                    <div className="card">
                      {question.answer_type === "multiple_choice" ? (
                        <div className="option-list">
                          {question.options.map((option) => (
                            <label key={option.id} className="radio">
                              <input
                                type={
                                  question.allow_multiple ? "checkbox" : "radio"
                                }
                                name={`q-${question.id}`}
                                checked={(
                                  selectedOptions[question.id] || []
                                ).includes(option.id)}
                                onChange={() =>
                                  toggleOption(
                                    question.id,
                                    option.id,
                                    question.allow_multiple
                                  )
                                }
                                disabled={submitted || expired}
                              />
                              <span>{option.option_text}</span>
                            </label>
                          ))}
                        </div>
                      ) : (
                        <textarea
                          className="monospace"
                          value={answerText[question.id] || ""}
                          onChange={(e) =>
                            handleAnswerChange(question.id, e.target.value)
                          }
                          disabled={submitted || expired}
                          placeholder="Type your answer..."
                        />
                      )}
                    </div>
                  </>
                );
              })()}
            </section>
          )}
        </>
      )}
      <div className="actions">
        <button
          onClick={() => setShowSubmitConfirm(true)}
          disabled={submitted || expired}
        >
          Submit
        </button>
      </div>

      <dialog ref={modalRef} className="modal">
        <p>
          Navigation change detected. This activity is recorded. Do you want to
          continue?
        </p>
        <form method="dialog">
          <button>Continue</button>
        </form>
      </dialog>

      {expired && !submitted && (
        <dialog open className="modal">
          <p>Time is up. Your answers are being submitted.</p>
        </dialog>
      )}

      {candidateToast && (
        <div className="toast candidate-toast">{candidateToast}</div>
      )}

      {showSubmitConfirm && (
        <div className="modal-overlay">
          <div className="modal-content">
            <header className="header">
              <h2>Submit Test?</h2>
            </header>
            <p>
              Once you submit, you will not be able to return to this test. Are
              you sure you want to submit your answers?
            </p>
            <div className="actions">
              <button onClick={handleSubmit}>Submit Test</button>
              <button
                className="ghost"
                onClick={() => setShowSubmitConfirm(false)}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function App() {
  const { role, login, logout } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!role) {
      navigate("/");
    }
  }, [role]);

  return (
    <Routes>
      <Route path="/" element={<LoginPage onLogin={login} />} />
      <Route
        path="/admin"
        element={<AdminDashboard onLogout={logout} />}
      />
      <Route
        path="/candidate"
        element={<CandidateDashboard onLogout={logout} />}
      />
      <Route path="/candidate/session" element={<CandidateSession />} />
    </Routes>
  );
}

