/**
 * NovaBorrow Marketing Bot - Multi-Instance Scalable Control Engine
 * Manages Parallel Worker Clusters (e.g. 2 JSONs per instance, multiple parallel workers)
 */

document.addEventListener("DOMContentLoaded", () => {
  // Authentication Elements
  const loginOverlay = document.getElementById("loginOverlay");
  const loginForm = document.getElementById("loginForm");
  const loginUser = document.getElementById("loginUser");
  const loginPass = document.getElementById("loginPass");
  const loginError = document.getElementById("loginError");
  const appContainer = document.getElementById("appContainer");
  const btnLogout = document.getElementById("btnLogout");
  const userDisplayName = document.getElementById("userDisplayName");

  // Global Header Status & Action Elements
  const globalStatusPill = document.getElementById("globalStatusPill");
  const globalStatusText = document.getElementById("globalStatusText");
  const btnStartAll = document.getElementById("btnStartAll");
  const btnStopAll = document.getElementById("btnStopAll");

  // Credentials Pool Elements
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("fileInput");
  const btnBrowseFiles = document.getElementById("btnBrowseFiles");
  const uploadProgress = document.getElementById("uploadProgress");
  const progressFill = document.getElementById("progressFill");
  const uploadStatusText = document.getElementById("uploadStatusText");
  const accountsRepoList = document.getElementById("accountsRepoList");
  const totalAccountsCount = document.getElementById("totalAccountsCount");

  // Multi-Instance Elements
  const instancesContainer = document.getElementById("instancesContainer");
  const btnAutoSplit2 = document.getElementById("btnAutoSplit2");
  const btnAddNewInstance = document.getElementById("btnAddNewInstance");

  // Terminal & Filter Elements
  const terminalOutput = document.getElementById("terminalOutput");
  const workerLogFilter = document.getElementById("workerLogFilter");
  const toggleAutoScroll = document.getElementById("toggleAutoScroll");
  const btnClearTerminal = document.getElementById("btnClearTerminal");
  const btnCopyTerminal = document.getElementById("btnCopyTerminal");

  // Stats Elements
  const statTotalComments = document.getElementById("statTotalComments");
  const statCommentedVideos = document.getElementById("statCommentedVideos");
  const statLeadReplies = document.getElementById("statLeadReplies");
  const statActiveWorkers = document.getElementById("statActiveWorkers");
  const recentActivityList = document.getElementById("recentActivityList");

  // OAuth Modal Elements
  const oauthModal = document.getElementById("oauthModal");
  const oauthAccountName = document.getElementById("oauthAccountName");
  const oauthAuthLink = document.getElementById("oauthAuthLink");
  const oauthCodeInput = document.getElementById("oauthCodeInput");
  const oauthStatusMsg = document.getElementById("oauthStatusMsg");
  const btnCloseOAuthModal = document.getElementById("btnCloseOAuthModal");
  const btnCancelOAuth = document.getElementById("btnCancelOAuth");
  const btnSubmitOAuthCode = document.getElementById("btnSubmitOAuthCode");

  // Instance Configuration Modal Elements
  const instanceModal = document.getElementById("instanceModal");
  const instanceModalTitle = document.getElementById("instanceModalTitle");
  const modalInstName = document.getElementById("modalInstName");
  const modalAccountsChecklist = document.getElementById("modalAccountsChecklist");
  const modalSelectedAccBadge = document.getElementById("modalSelectedAccBadge");
  const modalInstMode = document.getElementById("modalInstMode");
  const modalInstKeyword = document.getElementById("modalInstKeyword");
  const modalInstError = document.getElementById("modalInstError");
  const btnCloseInstModal = document.getElementById("btnCloseInstModal");
  const btnCancelInstModal = document.getElementById("btnCancelInstModal");
  const btnSaveInstModal = document.getElementById("btnSaveInstModal");

  // State
  let allAccounts = [];
  let instances = [];
  let currentOAuthSecret = null;
  let currentEditingInstId = null;
  let ws = null;
  let pollInterval = null;

  // --------------------------------------------------------------------------
  // 1. AUTHENTICATION
  // --------------------------------------------------------------------------
  async function checkAuth() {
    try {
      const res = await fetch("/api/auth/check");
      const data = await res.json();
      if (data.authenticated) {
        showApp(data.user);
      } else {
        showLogin();
      }
    } catch (e) {
      showLogin();
    }
  }

  function showLogin() {
    loginOverlay.classList.remove("hidden");
    loginOverlay.classList.add("active");
    appContainer.classList.add("hidden");
    if (ws) ws.close();
    if (pollInterval) clearInterval(pollInterval);
  }

  function showApp(username) {
    loginOverlay.classList.add("hidden");
    loginOverlay.classList.remove("active");
    appContainer.classList.remove("hidden");
    userDisplayName.textContent = username || "admin";
    loadAllData();
    initWebSocket();
    startStatusPolling();
  }

  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    loginError.classList.add("hidden");

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: loginUser.value,
          password: loginPass.value
        })
      });
      const data = await res.json();
      if (data.success) {
        showApp(data.user);
        showToast("Signed in successfully!", "success");
      } else {
        loginError.textContent = data.message || "Invalid credentials";
        loginError.classList.remove("hidden");
      }
    } catch (err) {
      loginError.textContent = "Error connecting to server";
      loginError.classList.remove("hidden");
    }
  });

  btnLogout.addEventListener("click", async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    showLogin();
    showToast("Logged out successfully", "success");
  });

  // --------------------------------------------------------------------------
  // 2. DATA LOADING (ACCOUNTS & INSTANCES)
  // --------------------------------------------------------------------------
  async function loadAllData() {
    await Promise.all([loadAccounts(), loadInstances()]);
  }

  async function loadAccounts() {
    try {
      const res = await fetch("/api/accounts");
      const data = await res.json();
      if (!data.success) return;

      allAccounts = data.accounts || [];
      totalAccountsCount.textContent = allAccounts.length;
      renderAccountsRepo();
    } catch (err) {
      console.error("Failed to load accounts:", err);
    }
  }

  function renderAccountsRepo() {
    if (allAccounts.length === 0) {
      accountsRepoList.innerHTML = `
        <div class="empty-state" style="padding: 2rem; text-align: center; color: var(--text-muted);">
          <p>No YouTube client secrets uploaded yet.</p>
          <p style="font-size: 0.8rem; margin-top: 4px;">Upload multiple JSON files above (e.g. 6 or more) to distribute across parallel instances.</p>
        </div>`;
      return;
    }

    accountsRepoList.innerHTML = allAccounts.map((acc, idx) => {
      const isAuth = acc.is_authenticated;
      return `
        <div class="account-card" data-filepath="${acc.filepath}">
          <div class="acc-left">
            <div class="acc-info">
              <div class="acc-name" title="${acc.filename}">
                #${idx + 1} <strong>${acc.project_id !== 'unknown' ? acc.project_id : acc.filename}</strong>
              </div>
              <div class="acc-meta">
                <span class="badge ${isAuth ? 'badge-auth' : 'badge-warning'}">
                  ${isAuth ? '🟢 Authenticated' : '🟡 Needs Auth'}
                </span>
                <span title="${acc.filepath}">File: ${acc.filename.length > 25 ? acc.filename.substring(0, 22) + '...' : acc.filename}</span>
              </div>
            </div>
          </div>
          <div class="acc-actions">
            ${!isAuth ? `
              <button class="btn btn-outline btn-xs btn-auth-account" data-filepath="${acc.filepath}" data-name="${acc.project_id}">
                🔐 Login
              </button>
            ` : `
              <button class="btn btn-ghost btn-xs btn-auth-account" data-filepath="${acc.filepath}" data-name="${acc.project_id}" title="Re-auth">
                🔄
              </button>
            `}
            <button class="btn btn-ghost btn-xs btn-del-account" data-filepath="${acc.filepath}" title="Remove file" style="color: var(--accent-rose);">
              &times;
            </button>
          </div>
        </div>
      `;
    }).join("");

    // Attach OAuth and Delete buttons
    document.querySelectorAll(".btn-auth-account").forEach(btn => {
      btn.addEventListener("click", () => {
        openOAuthModal(btn.getAttribute("data-filepath"), btn.getAttribute("data-name"));
      });
    });

    document.querySelectorAll(".btn-del-account").forEach(btn => {
      btn.addEventListener("click", async () => {
        if (confirm("Are you sure you want to delete this credentials file?")) {
          await deleteAccount(btn.getAttribute("data-filepath"));
        }
      });
    });
  }

  // --------------------------------------------------------------------------
  // 3. MULTI-INSTANCE PARALLEL WORKERS MANAGER
  // --------------------------------------------------------------------------
  async function loadInstances() {
    try {
      const res = await fetch("/api/instances");
      const data = await res.json();
      if (!data.success) return;

      instances = data.instances || [];
      updateGlobalStatus(data.running_count || 0);
      renderInstances();
      updateFilterDropdown();
    } catch (err) {
      console.error("Failed to load instances:", err);
    }
  }

  function updateGlobalStatus(runningCount) {
    statActiveWorkers.textContent = runningCount;
    if (runningCount > 0) {
      globalStatusPill.querySelector(".status-dot").className = "status-dot running";
      globalStatusText.textContent = `${runningCount} Parallel Worker${runningCount > 1 ? 's' : ''} Active`;
      btnStartAll.classList.add("hidden");
      btnStopAll.classList.remove("hidden");
    } else {
      globalStatusPill.querySelector(".status-dot").className = "status-dot stopped";
      globalStatusText.textContent = "0 Workers Active";
      btnStartAll.classList.remove("hidden");
      btnStopAll.classList.add("hidden");
    }
  }

  function renderInstances() {
    if (instances.length === 0) {
      instancesContainer.innerHTML = `
        <div class="empty-state" style="padding: 2rem; text-align: center; color: var(--text-muted);">
          <p>No parallel instances configured.</p>
          <button class="btn btn-primary btn-sm mt-4" id="btnEmptyCreate">➕ Create First Instance</button>
        </div>`;
      document.getElementById("btnEmptyCreate")?.addEventListener("click", createNewInstance);
      return;
    }

    instancesContainer.innerHTML = instances.map((inst, idx) => {
      const isRunning = inst.status === "running";
      const assignedPaths = new Set(inst.accounts || []);

      return `
        <div class="instance-card ${isRunning ? 'running' : ''}" data-inst-id="${inst.id}">
          <div class="inst-header">
            <div class="inst-title-box">
              <span class="status-dot ${isRunning ? 'running' : 'stopped'}"></span>
              <input type="text" class="inst-title-input" value="${inst.name || 'Instance #' + (idx + 1)}" data-inst-id="${inst.id}" title="Click to rename instance">
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
              <span class="inst-status-badge ${isRunning ? 'running' : 'stopped'}">
                ${isRunning ? `🟢 Running (PID: ${inst.pid})` : '⚪ Idle'}
              </span>
              <button class="btn btn-outline btn-xs btn-edit-inst" data-inst-id="${inst.id}" title="Choose which YouTube Accounts to run in this instance">
                ⚙️ Choose Accounts
              </button>
              <button class="btn btn-ghost btn-xs btn-delete-inst" data-inst-id="${inst.id}" title="Delete Instance" style="color: var(--accent-rose);">
                🗑️
              </button>
            </div>
          </div>

          <div class="inst-body">
            <!-- Account Assignment Chips -->
            <div class="inst-accounts-selector">
              <label>Assigned YouTube Accounts (${assignedPaths.size} selected):</label>
              <div class="inst-acc-chips">
                ${allAccounts.map(acc => {
                  const isAssigned = assignedPaths.has(acc.filepath) || assignedPaths.has(acc.filename);
                  return `
                    <button type="button" class="acc-chip-toggle ${isAssigned ? 'active' : ''}" 
                            data-inst-id="${inst.id}" data-filepath="${acc.filepath}" 
                            title="${acc.filename}">
                      ${isAssigned ? '☑' : '☐'} ${acc.project_id !== 'unknown' ? acc.project_id : acc.filename.substring(0, 15)}
                    </button>
                  `;
                }).join("")}
              </div>
            </div>

            <!-- Instance Execution Controls -->
            <div class="inst-actions">
              ${isRunning ? `
                <button class="btn btn-danger btn-sm btn-stop-inst" data-inst-id="${inst.id}">
                  ⏹ Stop Instance
                </button>
              ` : `
                <button class="btn btn-success btn-sm btn-start-inst" data-inst-id="${inst.id}">
                  ▶ Start Instance
                </button>
              `}
            </div>
          </div>
        </div>
      `;
    }).join("");

    // Attach instance renaming
    document.querySelectorAll(".inst-title-input").forEach(input => {
      input.addEventListener("change", async (e) => {
        const iid = e.target.getAttribute("data-inst-id");
        const inst = instances.find(i => i.id === iid);
        if (inst) {
          inst.name = e.target.value.trim();
          await saveInstancesToServer();
          updateFilterDropdown();
        }
      });
    });

    // Attach account chip toggling for each instance
    document.querySelectorAll(".acc-chip-toggle").forEach(btn => {
      btn.addEventListener("click", async () => {
        const iid = btn.getAttribute("data-inst-id");
        const fp = btn.getAttribute("data-filepath");
        const inst = instances.find(i => i.id === iid);
        if (!inst) return;

        inst.accounts = inst.accounts || [];
        const idx = inst.accounts.indexOf(fp);
        if (idx > -1) {
          inst.accounts.splice(idx, 1);
        } else {
          inst.accounts.push(fp);
        }
        await saveInstancesToServer();
        renderInstances();
      });
    });

    // Attach Edit Instance / Choose Accounts button
    document.querySelectorAll(".btn-edit-inst").forEach(btn => {
      btn.addEventListener("click", () => {
        const iid = btn.getAttribute("data-inst-id");
        const inst = instances.find(i => i.id === iid);
        if (inst) openInstanceModal(inst);
      });
    });

    // Attach Start Instance button
    document.querySelectorAll(".btn-start-inst").forEach(btn => {
      btn.addEventListener("click", async () => {
        const iid = btn.getAttribute("data-inst-id");
        await startInstance(iid);
      });
    });

    // Attach Stop Instance button
    document.querySelectorAll(".btn-stop-inst").forEach(btn => {
      btn.addEventListener("click", async () => {
        const iid = btn.getAttribute("data-inst-id");
        await stopInstance(iid);
      });
    });

    // Attach Delete Instance button
    document.querySelectorAll(".btn-delete-inst").forEach(btn => {
      btn.addEventListener("click", async () => {
        const iid = btn.getAttribute("data-inst-id");
        if (confirm("Delete this instance configuration?")) {
          await deleteInstance(iid);
        }
      });
    });
  }

  function updateFilterDropdown() {
    const currentVal = workerLogFilter.value;
    workerLogFilter.innerHTML = `<option value="all">⚡ All Workers (Combined)</option>` +
      instances.map(inst => `<option value="${inst.id}">${inst.name}</option>`).join("");
    if (currentVal && [...workerLogFilter.options].some(o => o.value === currentVal)) {
      workerLogFilter.value = currentVal;
    }
  }

  async function saveInstancesToServer() {
    try {
      await fetch("/api/instances/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ instances })
      });
    } catch (e) {
      console.error("Error saving instances:", e);
    }
  }

  async function startInstance(iid) {
    const inst = instances.find(i => i.id === iid);
    if (!inst || !inst.accounts || inst.accounts.length === 0) {
      showToast("Please assign at least 1 YouTube account to this instance!", "error");
      return;
    }

    try {
      const res = await fetch("/api/instances/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ instance_id: iid })
      });
      const data = await res.json();
      if (data.success) {
        showToast(`🚀 ${inst.name} started! (PID: ${data.pid})`, "success");
        await loadInstances();
      } else {
        showToast(data.message || "Failed to start instance", "error");
      }
    } catch (e) {
      showToast("Network error starting instance", "error");
    }
  }

  async function stopInstance(iid) {
    try {
      const res = await fetch("/api/instances/stop", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ instance_id: iid })
      });
      const data = await res.json();
      if (data.success) {
        showToast("Instance stopped", "success");
        await loadInstances();
      } else {
        showToast(data.message || "Failed to stop instance", "error");
      }
    } catch (e) {
      showToast("Network error stopping instance", "error");
    }
  }

  // Auto-Split 2 Accounts Per Instance
  btnAutoSplit2.addEventListener("click", async () => {
    if (allAccounts.length === 0) {
      showToast("No accounts available to auto-split! Upload JSONs first.", "error");
      return;
    }
    if (confirm(`Automatically group all ${allAccounts.length} accounts into parallel instances of 2 accounts each?`)) {
      try {
        const res = await fetch("/api/instances/auto-split", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ accounts_per_instance: 2 })
        });
        const data = await res.json();
        if (data.success) {
          showToast(data.message, "success");
          await loadInstances();
        } else {
          showToast(data.message || "Auto-split failed", "error");
        }
      } catch (e) {
        showToast("Error during auto-split", "error");
      }
    }
  });

  // --------------------------------------------------------------------------
  // INSTANCE CREATION & CONFIGURATION MODAL (CHOOSE MULTIPLE ACCOUNTS)
  // --------------------------------------------------------------------------
  function openInstanceModal(targetInst = null) {
    modalInstError.classList.add("hidden");
    const isEdit = targetInst !== null;
    currentEditingInstId = isEdit ? targetInst.id : null;

    if (isEdit) {
      instanceModalTitle.textContent = `⚙️ Configure ${targetInst.name || 'Instance'}`;
      modalInstName.value = targetInst.name || "";
      modalInstMode.value = targetInst.mode || "hybrid";
      modalInstKeyword.value = targetInst.keyword || "";
    } else {
      instanceModalTitle.textContent = `➕ Create New Parallel Instance`;
      modalInstName.value = `Instance #${instances.length + 1} (Worker ${instances.length + 1})`;
      modalInstMode.value = "hybrid";
      modalInstKeyword.value = "";
    }

    const assignedSet = new Set(isEdit ? (targetInst.accounts || []) : []);

    if (allAccounts.length === 0) {
      modalAccountsChecklist.innerHTML = `
        <div style="padding: 1.5rem; text-align: center; color: var(--text-muted);">
          No accounts found. Please upload <code>client_secret*.json</code> files first.
        </div>`;
      modalSelectedAccBadge.textContent = "0 Accounts Selected";
    } else {
      modalAccountsChecklist.innerHTML = `
        <div style="display: flex; gap: 8px; margin-bottom: 10px;">
          <button type="button" class="btn btn-outline btn-xs" id="btnModalSelect2">⚡ Select 2 Accounts</button>
          <button type="button" class="btn btn-outline btn-xs" id="btnModalSelectAll">Select All</button>
          <button type="button" class="btn btn-outline btn-xs" id="btnModalClear">Clear</button>
        </div>
        ` + allAccounts.map((acc, idx) => {
        const isChecked = assignedSet.has(acc.filepath) || assignedSet.has(acc.filename);
        return `
          <div class="account-card" style="padding: 10px 14px; margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between;">
            <div style="display: flex; align-items: center; gap: 12px; cursor: pointer;">
              <input type="checkbox" id="mcb_${idx}" class="modal-acc-cb" data-filepath="${acc.filepath}" ${isChecked ? 'checked' : ''} style="width: 18px; height: 18px; cursor: pointer;">
              <label for="mcb_${idx}" style="cursor: pointer; margin-bottom: 0;">
                <div style="font-weight: 600; font-size: 0.92rem; color: var(--text-main);">
                  ${acc.project_id !== 'unknown' ? acc.project_id : acc.filename}
                </div>
                <div style="font-size: 0.75rem; color: var(--text-muted);">File: ${acc.filename}</div>
              </label>
            </div>
            <span class="badge ${acc.is_authenticated ? 'badge-auth' : 'badge-warning'}">
              ${acc.is_authenticated ? '🟢 Ready' : '🟡 Needs Auth'}
            </span>
          </div>
        `;
      }).join("");

      updateModalBadge();

      // Listen on modal checkboxes
      document.querySelectorAll(".modal-acc-cb").forEach(cb => {
        cb.addEventListener("change", updateModalBadge);
      });

      // Presets
      document.getElementById("btnModalSelect2")?.addEventListener("click", () => {
        document.querySelectorAll(".modal-acc-cb").forEach((cb, i) => { cb.checked = (i < 2); });
        updateModalBadge();
      });
      document.getElementById("btnModalSelectAll")?.addEventListener("click", () => {
        document.querySelectorAll(".modal-acc-cb").forEach(cb => { cb.checked = true; });
        updateModalBadge();
      });
      document.getElementById("btnModalClear")?.addEventListener("click", () => {
        document.querySelectorAll(".modal-acc-cb").forEach(cb => { cb.checked = false; });
        updateModalBadge();
      });
    }

    instanceModal.classList.remove("hidden");
  }

  function updateModalBadge() {
    const checkedCount = document.querySelectorAll(".modal-acc-cb:checked").length;
    modalSelectedAccBadge.textContent = `${checkedCount} Account${checkedCount !== 1 ? 's' : ''} Selected`;
  }

  function closeInstanceModal() {
    instanceModal.classList.add("hidden");
    currentEditingInstId = null;
  }

  btnCloseInstModal.addEventListener("click", closeInstanceModal);
  btnCancelInstModal.addEventListener("click", closeInstanceModal);

  btnSaveInstModal.addEventListener("click", async () => {
    modalInstError.classList.add("hidden");

    const name = modalInstName.value.trim() || `Instance #${instances.length + 1}`;
    const mode = modalInstMode.value;
    const keyword = modalInstKeyword.value.trim();

    const selectedFilepaths = Array.from(document.querySelectorAll(".modal-acc-cb:checked"))
      .map(cb => cb.getAttribute("data-filepath"));

    if (selectedFilepaths.length === 0) {
      modalInstError.textContent = "Please checkmark (tick) at least 1 YouTube Account for this instance!";
      modalInstError.classList.remove("hidden");
      return;
    }

    if (currentEditingInstId) {
      // Edit existing
      const target = instances.find(i => i.id === currentEditingInstId);
      if (target) {
        target.name = name;
        target.mode = mode;
        target.keyword = keyword;
        target.accounts = selectedFilepaths;
      }
    } else {
      // Create new
      const newInst = {
        id: `inst_${Date.now().toString(36)}`,
        name: name,
        accounts: selectedFilepaths,
        mode: mode,
        keyword: keyword,
        max_comments: 25,
        min_delay: 30,
        max_delay: 60,
        public_search: true,
        ignore_history: false
      };
      instances.push(newInst);
    }

    await saveInstancesToServer();
    closeInstanceModal();
    renderInstances();
    updateFilterDropdown();
    showToast(`Instance saved with ${selectedFilepaths.length} YouTube account(s)!`, "success");
  });

  btnAddNewInstance.addEventListener("click", () => openInstanceModal(null));

  async function deleteInstance(iid) {
    try {
      const res = await fetch("/api/instances/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ instance_id: iid })
      });
      const data = await res.json();
      if (data.success) {
        showToast("Instance deleted", "success");
        await loadInstances();
      }
    } catch (e) {
      showToast("Error deleting instance", "error");
    }
  }

  // Start All / Stop All
  btnStartAll.addEventListener("click", async () => {
    btnStartAll.disabled = true;
    try {
      const res = await fetch("/api/instances/start-all", { method: "POST" });
      const data = await res.json();
      if (data.success) {
        showToast(data.message, "success");
        await loadInstances();
      } else {
        showToast(data.message || "Failed to start all instances", "error");
      }
    } catch (e) {
      showToast("Network error starting all", "error");
    } finally {
      btnStartAll.disabled = false;
    }
  });

  btnStopAll.addEventListener("click", async () => {
    btnStopAll.disabled = true;
    try {
      const res = await fetch("/api/instances/stop-all", { method: "POST" });
      const data = await res.json();
      if (data.success) {
        showToast("All instances stopped", "success");
        await loadInstances();
      }
    } catch (e) {
      showToast("Network error stopping all", "error");
    } finally {
      btnStopAll.disabled = false;
    }
  });

  // --------------------------------------------------------------------------
  // 4. MULTI-FILE UPLOAD (DRAG & DROP)
  // --------------------------------------------------------------------------
  btnBrowseFiles.addEventListener("click", () => fileInput.click());

  dropzone.addEventListener("click", (e) => {
    if (e.target !== btnBrowseFiles) fileInput.click();
  });

  ["dragenter", "dragover"].forEach(evtName => {
    dropzone.addEventListener(evtName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach(evtName => {
    dropzone.addEventListener(evtName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove("dragover");
    });
  });

  dropzone.addEventListener("drop", (e) => {
    const files = e.dataTransfer.files;
    if (files.length > 0) handleFilesUpload(files);
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) handleFilesUpload(e.target.files);
  });

  async function handleFilesUpload(files) {
    const formData = new FormData();
    let validCount = 0;

    for (let i = 0; i < files.length; i++) {
      const f = files[i];
      if (f.name.endsWith(".json") || f.name.endsWith(".pickle")) {
        formData.append("files", f);
        validCount++;
      }
    }

    if (validCount === 0) {
      showToast("Please upload .json or .pickle files only!", "error");
      return;
    }

    uploadProgress.classList.remove("hidden");
    progressFill.style.width = "40%";
    uploadStatusText.textContent = `Uploading ${validCount} file(s)...`;

    try {
      const res = await fetch("/api/accounts/upload", {
        method: "POST",
        body: formData
      });
      const data = await res.json();

      progressFill.style.width = "100%";
      if (data.success) {
        uploadStatusText.textContent = "Upload complete!";
        showToast(`Successfully uploaded ${data.files.length} file(s)!`, "success");
        setTimeout(() => {
          uploadProgress.classList.add("hidden");
          progressFill.style.width = "0%";
        }, 1500);
        await loadAllData();
      } else {
        uploadStatusText.textContent = "Upload failed";
        showToast(data.message || "Upload failed", "error");
      }
    } catch (e) {
      uploadStatusText.textContent = "Upload error";
      showToast("Upload network error", "error");
    }
  }

  async function deleteAccount(filepath) {
    try {
      const res = await fetch("/api/accounts/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filepath })
      });
      const data = await res.json();
      if (data.success) {
        showToast("Account removed successfully", "success");
        await loadAllData();
      } else {
        showToast(data.error || "Failed to delete account", "error");
      }
    } catch (err) {
      showToast("Error deleting account", "error");
    }
  }

  // --------------------------------------------------------------------------
  // 5. GOOGLE OAUTH MODAL & CODE SUBMISSION
  // --------------------------------------------------------------------------
  async function openOAuthModal(filepath, name) {
    currentOAuthSecret = filepath;
    oauthAccountName.textContent = name || filepath;
    oauthCodeInput.value = "";
    oauthStatusMsg.classList.add("hidden");
    oauthModal.classList.remove("hidden");

    try {
      const res = await fetch("/api/accounts/oauth-url", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filepath })
      });
      const data = await res.json();
      if (data.success && data.auth_url) {
        oauthAuthLink.href = data.auth_url;
      } else {
        oauthStatusMsg.textContent = "Could not generate OAuth link: " + (data.error || "Unknown error");
        oauthStatusMsg.className = "alert-box error";
        oauthStatusMsg.classList.remove("hidden");
      }
    } catch (e) {
      oauthStatusMsg.textContent = "Network error loading OAuth URL";
      oauthStatusMsg.className = "alert-box error";
      oauthStatusMsg.classList.remove("hidden");
    }
  }

  function closeOAuthModal() {
    oauthModal.classList.add("hidden");
    currentOAuthSecret = null;
  }

  btnCloseOAuthModal.addEventListener("click", closeOAuthModal);
  btnCancelOAuth.addEventListener("click", closeOAuthModal);

  btnSubmitOAuthCode.addEventListener("click", async () => {
    const code = oauthCodeInput.value.trim();
    if (!code) {
      oauthStatusMsg.textContent = "Please enter the authorization code or redirect URL!";
      oauthStatusMsg.className = "alert-box error";
      oauthStatusMsg.classList.remove("hidden");
      return;
    }

    oauthStatusMsg.textContent = "Verifying code & generating token...";
    oauthStatusMsg.className = "alert-box";
    oauthStatusMsg.classList.remove("hidden");

    try {
      const res = await fetch("/api/accounts/oauth-code", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          filepath: currentOAuthSecret,
          code: code
        })
      });
      const data = await res.json();
      if (data.success) {
        oauthStatusMsg.textContent = data.message;
        oauthStatusMsg.className = "alert-box success";
        showToast("Account authenticated successfully!", "success");
        setTimeout(() => {
          closeOAuthModal();
          loadAccounts();
        }, 1200);
      } else {
        oauthStatusMsg.textContent = data.error || "Failed to exchange code";
        oauthStatusMsg.className = "alert-box error";
      }
    } catch (e) {
      oauthStatusMsg.textContent = "Network error saving token";
      oauthStatusMsg.className = "alert-box error";
    }
  });

  // --------------------------------------------------------------------------
  // 6. WEBSOCKET LOGS STREAMING (WITH INSTANCE TAGS & FILTER)
  // --------------------------------------------------------------------------
  function initWebSocket() {
    if (ws && ws.readyState === WebSocket.OPEN) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/logs`;

    ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "log") {
          appendLog(msg.data, msg.instance_id, msg.instance_name);
        }
      } catch (e) {
        appendLog(event.data, "system", "SYSTEM");
      }
    };

    ws.onclose = () => {
      setTimeout(initWebSocket, 4000);
    };
  }

  function getTagClass(name) {
    if (!name) return "tag-inst-1";
    if (name.includes("1")) return "tag-inst-1";
    if (name.includes("2")) return "tag-inst-2";
    if (name.includes("3")) return "tag-inst-3";
    if (name.includes("4")) return "tag-inst-4";
    return "tag-inst-5";
  }

  function appendLog(line, instanceId = "system", instanceName = "SYSTEM") {
    // Respect worker log filter
    const activeFilter = workerLogFilter.value;
    if (activeFilter !== "all" && instanceId !== "system" && instanceId !== activeFilter) {
      return;
    }

    const lineEl = document.createElement("div");
    lineEl.className = "terminal-line";
    lineEl.setAttribute("data-instance-id", instanceId);

    const tagClass = getTagClass(instanceName);
    const tagHtml = `<span class="worker-tag ${tagClass}">[${instanceName}]</span>`;

    let styledContent = line;
    if (line.includes("POSTED") || line.includes("SUCCESS") || line.includes("successfully")) {
      lineEl.style.color = "var(--accent-emerald)";
      lineEl.style.fontWeight = "600";
    } else if (line.includes("QUOTA EXHAUSTED") || line.includes("WARNING")) {
      lineEl.style.color = "var(--accent-amber)";
    } else if (line.includes("SYSTEM") || line.includes("NOVA BORROW")) {
      lineEl.style.color = "var(--primary)";
    } else if (line.includes("ERROR") || line.includes("missing")) {
      lineEl.style.color = "var(--accent-rose)";
    }

    lineEl.innerHTML = `${tagHtml} ${styledContent}`;
    terminalOutput.appendChild(lineEl);

    if (toggleAutoScroll.checked) {
      terminalOutput.scrollTop = terminalOutput.scrollHeight;
    }
  }

  btnClearTerminal.addEventListener("click", () => {
    terminalOutput.innerHTML = "";
  });

  btnCopyTerminal.addEventListener("click", () => {
    navigator.clipboard.writeText(terminalOutput.innerText).then(() => {
      showToast("Logs copied to clipboard!", "success");
    });
  });

  workerLogFilter.addEventListener("change", () => {
    // Re-filter terminal lines
    const activeFilter = workerLogFilter.value;
    document.querySelectorAll(".terminal-line").forEach(lineEl => {
      const iid = lineEl.getAttribute("data-instance-id");
      if (activeFilter === "all" || iid === "system" || iid === activeFilter) {
        lineEl.style.display = "block";
      } else {
        lineEl.style.display = "none";
      }
    });
  });

  // --------------------------------------------------------------------------
  // 7. STATUS & ACTIVITY POLLING
  // --------------------------------------------------------------------------
  function startStatusPolling() {
    fetchStatus();
    pollInterval = setInterval(fetchStatus, 4000);
  }

  async function fetchStatus() {
    try {
      const res = await fetch("/api/bot/status");
      const data = await res.json();
      updateGlobalStatus(data.running_instances_count || 0);

      const supabasePill = document.getElementById("supabasePill");
      const supabasePillText = document.getElementById("supabasePillText");
      if (supabasePill && supabasePillText) {
        if (data.database === "supabase") {
          supabasePillText.textContent = "⚡ Supabase Live";
          supabasePill.classList.add("supabase-pill");
        } else {
          supabasePillText.textContent = "📁 Local Fallback";
        }
      }

      if (data.stats) {
        if (statTotalComments) statTotalComments.textContent = data.stats.total_comments_posted || 0;
        statCommentedVideos.textContent = data.stats.total_commented_videos || 0;
        statLeadReplies.textContent = data.stats.total_lead_replies || 0;
      }

      if (data.recent_activity && recentActivityList) {
        if (data.recent_activity.length === 0) {
          recentActivityList.innerHTML = `<div class="empty-state" style="padding: 1rem; text-align: center; color: var(--text-muted);">No recent comments yet.</div>`;
        } else {
          recentActivityList.innerHTML = data.recent_activity.map(item => `
            <div class="activity-item">
              <div class="activity-info">
                <div class="activity-title" title="${item.title}">${item.title}</div>
                <div class="activity-meta">
                  <span>📺 ${item.channel}</span>
                  <span>🕒 ${new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                </div>
              </div>
              <div class="activity-badges">
                ${(item.accounts || []).map(acc => `<span class="acc-pill">👤 ${acc}</span>`).join('')}
              </div>
            </div>
          `).join('');
        }
      }
    } catch (e) {}
  }

  // --------------------------------------------------------------------------
  // 8. TOAST NOTIFICATIONS HELPER
  // --------------------------------------------------------------------------
  function showToast(message, type = "success") {
    const toastContainer = document.getElementById("toastContainer");
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.textContent = message;
    toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(50px)";
      toast.style.transition = "all 0.3s ease";
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }

  // Initialize
  checkAuth();
});
