-- The zero-LSP measurement for the starter the installer placed (24.1 D-12/D-13). It runs from a
-- directory holding a.py, a.lua, a.ts, a.go and A.java, in a headless nvim started after a first
-- launch installed the plugins:
--   nvim --headless -c "luafile scripts/nvim-lsp-check.lua"
-- It prints one `NVIM_LSP clients=... mason_entries=... filetypes=... lspconfig=... mason=...` line,
-- plus a `PROC <cmdline>` line per language-server process, then quits. container-e2e-verify.sh
-- (`nvim-lsp`) turns those lines into a verdict.

local SERVER_PATTERNS = {
  'language-server',
  'lua-language',
  'pyright',
  'gopls',
  'jdtls',
  'tsserver',
  'typescript-language',
  'stylua',
}

-- Command lines of live processes that look like a language server. Run while this nvim is still
-- alive: a server it started would die with it.
local function server_processes()
  local found = {}
  local self_pid = tostring(vim.fn.getpid())
  for _, dir in ipairs(vim.fn.glob('/proc/[0-9]*', false, true)) do
    if vim.fn.fnamemodify(dir, ':t') ~= self_pid then
      local file = io.open(dir .. '/cmdline', 'rb')
      if file then
        local cmdline = file:read('*a') or ''
        file:close()
        cmdline = cmdline:gsub('%z', ' ')
        for _, pattern in ipairs(SERVER_PATTERNS) do
          if cmdline:find(pattern, 1, true) then
            found[#found + 1] = cmdline
            break
          end
        end
      end
    end
  end
  return found
end

local function count_entries(dir)
  return #vim.fn.glob(dir .. '/*', false, true)
end

local function run()
  local filetypes = {}
  for _, name in ipairs { 'a.py', 'a.lua', 'a.ts', 'a.go', 'A.java' } do
    vim.cmd.edit(name)
    filetypes[#filetypes + 1] = vim.bo.filetype
  end
  -- A bounded poll, not a sleep: it ends the moment any client attaches.
  vim.wait(8000, function() return #vim.lsp.get_clients() > 0 end, 200)

  local data = vim.fn.stdpath('data')
  local plugins = data .. '/site/pack/core/opt/'
  local lspconfig = vim.fn.isdirectory(plugins .. 'nvim-lspconfig')
  local mason = vim.fn.isdirectory(plugins .. 'mason.nvim')
  for _, cmdline in ipairs(server_processes()) do
    io.stdout:write('PROC ', cmdline, '\n')
  end
  io.stdout:write(
    string.format(
      'NVIM_LSP clients=%d mason_entries=%d filetypes=%s lspconfig=%d mason=%d\n',
      #vim.lsp.get_clients(),
      count_entries(data .. '/mason/packages'),
      table.concat(filetypes, ','),
      lspconfig,
      mason
    )
  )
  io.stdout:flush()
  vim.cmd('qa!')
end

-- `-c` commands run before VimEnter (:h startup, step 19), so wait for it unless it already fired.
if vim.v.vim_did_enter == 1 then
  run()
else
  vim.api.nvim_create_autocmd('VimEnter', {
    once = true,
    callback = function() vim.schedule(run) end,
  })
end
