const { contextBridge, ipcRenderer } = require('electron');

const invoke = (ch) => (...args) => ipcRenderer.invoke(ch, ...args);
const on = (ch) => (cb) => {
  const listener = (_e, payload) => cb(payload);
  ipcRenderer.on(ch, listener);
  return () => ipcRenderer.removeListener(ch, listener);
};

contextBridge.exposeInMainWorld('tuff', {
  settings: { get: invoke('settings:get'), set: invoke('settings:set') },
  project: { default: invoke('project:default'), openFolder: invoke('dialog:openFolder') },
  fs: {
    readDir: invoke('fs:readDir'),
    listAll: invoke('fs:listAll'),
    readFile: invoke('fs:readFile'),
    writeFile: invoke('fs:writeFile'),
    exists: invoke('fs:exists'),
    createFile: invoke('fs:createFile'),
    createDir: invoke('fs:createDir'),
    rename: invoke('fs:rename'),
    trash: invoke('fs:trash'),
    reveal: invoke('shell:reveal'),
    search: invoke('fs:search'),
    replaceInFile: invoke('fs:replaceInFile'),
    watch: invoke('fs:watch'),
    writeFilesSync: (files) => ipcRenderer.sendSync('fs:writeFilesSync', files),
    onChanged: on('fs:changed'),
  },
  run: { start: invoke('run:start'), stop: invoke('run:stop'), input: invoke('run:input'), onData: on('run:data'), onExit: on('run:exit') },
  run2: { start: invoke('run2:start'), stop: invoke('run2:stop'), onData: on('run2:data'), onExit: on('run2:exit') },
  debug: { send: invoke('debug:send'), onEvent: on('debug:event') }, // 1.5.0: a run with the debugger (run.start's opts.debug)
  build: {
    start: invoke('build:start'),
    cancel: invoke('build:cancel'),
    iconPreview: invoke('build:iconPreview'),
    chooseIcon: invoke('dialog:openImage'),
    openPath: invoke('shell:openPath'),
    onEvent: on('build:event'),
  },
  update: {
    state: invoke('update:state'),
    check: invoke('update:check'),
    install: invoke('update:install'),
    restart: invoke('update:restart'),
    reschedule: invoke('update:reschedule'),
    onStatus: on('update:status'),
  },
  plugins: {
    list: invoke('plugins:list'),
    install: invoke('plugins:install'),
    uninstall: invoke('plugins:uninstall'),
    setEnabled: invoke('plugins:setEnabled'),
    writeFile: invoke('plugins:writeFile'),
    request: invoke('plugins:request'),
  },
  agents: {
    detect: invoke('agents:detect'),
    connection: invoke('agents:connection'),
    connect: invoke('agents:connect'),
    mcpServer: invoke('agents:mcpServer'),
    mcpSetup: invoke('agents:mcpSetup'),
    mcpCheck: invoke('agents:mcpCheck'),
    signedIn: invoke('agents:signedIn'),
    signIn: invoke('agents:signIn'),
    models: invoke('agents:models'),
    run: invoke('agents:run'),
    stop: invoke('agents:stop'),
    onEvent: on('agents:event'),
    ai: {
      status: invoke('ai:status'),
      download: invoke('ai:download'),
      cancel: invoke('ai:cancel'),
      remove: invoke('ai:remove'),
      onProgress: on('ai:progress'),
    },
  },
  version: invoke('app:version'),
  checkSource: invoke('tuff:check'),
  engine: { scene: invoke('engine:scene') },
  openRepo: (url) => ipcRenderer.invoke('shell:openExternal', url),
  openWeb: (url) => ipcRenderer.invoke('shell:openWeb', url),
  win: {
    minimize: invoke('window:minimize'),
    toggleMaximize: invoke('window:toggleMaximize'),
    close: invoke('window:close'),
    isMaximized: invoke('window:isMaximized'),
    onMaximized: on('window:maximized'),
    onBlur: on('window:blur'),
    onFullScreen: on('window:fullscreen'),
    devtools: invoke('app:devtools'),
  },
  platform: process.platform,
  sep: process.platform === 'win32' ? '\\' : '/',
});
