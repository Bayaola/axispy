AI Assistant Tutorial
=====================

This tutorial covers AxisPy's built-in AI Assistant that helps you write scripts, understand the engine API, and even modify your project directly through natural language conversations.

.. contents:: On this page
   :local:
   :depth: 2

Overview
--------

The AI Assistant is integrated directly into the AxisPy editor and can:

- Help write and edit scripts using the engine's API
- Answer questions about how to use components and systems
- Create entities and add components to your scene
- Read your existing scripts and suggest improvements
- Debug issues by examining your project structure

The assistant uses an LLM provider (OpenAI, Anthropic, Google, OpenRouter, or local) and has access to a set of **tools** that let it interact with your project files directly.

Editor workflow (no code)
-------------------------

- **Configure AI Provider (Project Settings)**
  - Project → Project Settings → AI tab.
  - Select a **Provider**: OpenAI, OpenRouter, Local, Google, Anthropic, or NVIDIA.
  - Enter your **API Key** for the selected provider.
  - Choose a **Model** (e.g., ``gpt-4o-mini``, ``claude-3-5-sonnet-latest``, ``gemini-2.5-flash``).
  - Click "Save" to persist settings to ``project.config``.

- **Open the AI Assistant (AI Assistant Dock)**
  - View → AI Assistant (or use the robot icon in the toolbar).
  - The dock appears on the right side of the editor by default.
  - The assistant shows its model status at the top.

- **Managing Sessions**
  - Use the session dropdown to switch between previous conversations.
  - Click the **+** button to start a new session.
  - Click the trash icon to delete a session.
  - Sessions are saved automatically and persist across editor restarts.

- **Chatting with the Assistant**
  - Type your message in the text area at the bottom.
  - Press **Enter** (or Ctrl+Enter) to send.
  - The assistant streams its response in real-time.
  - Code blocks are syntax-highlighted; click **Apply** on diff widgets to accept file changes.

- **Using AI Tools**
  - The assistant can invoke tools to inspect and modify your project:
    - ``list_entities()`` — see all entities in the scene
    - ``get_entity_info(name)`` — inspect a specific entity
    - ``read_script(path)`` — view script source
    - ``write_script(path, content)`` — create new scripts
    - ``edit_script(path, old, new)`` — modify existing scripts
    - ``create_entity(name, components)`` — add entities to the scene
    - ``add_component_to_entity(entity, component)`` — attach components
  - When the assistant uses a tool, you'll see a notification in the chat.

Configuring AI Providers
------------------------

The AI Assistant supports multiple LLM providers. Choose the one that fits your needs:

**OpenAI**
  - API Key: Get from `platform.openai.com <https://platform.openai.com>`_
  - Models: ``gpt-4o-mini`` (default), ``gpt-4o``, ``gpt-4-turbo``, etc.
  - Base URL: ``https://api.openai.com/v1`` (or your own proxy)

**Anthropic (Claude)**
  - API Key: Get from `console.anthropic.com <https://console.anthropic.com>`_
  - Models: ``claude-3-5-sonnet-latest`` (default), ``claude-3-opus-latest``, etc.
  - No base URL needed (uses default Anthropic endpoint)

**Google (Gemini)**
  - API Key: Get from `aistudio.google.com <https://aistudio.google.com>`_
  - Models: ``gemini-2.5-flash`` (default), ``gemini-2.0-flash``, etc.

**OpenRouter**
  - API Key: Get from `openrouter.ai <https://openrouter.ai>`_ (free tier available)
  - Models: Access to 300+ models including DeepSeek, Claude, GPT, etc.
  - Example model: ``deepseek/deepseek-chat:free``
  - Base URL: ``https://openrouter.ai/api/v1``

**Local LLM (Ollama / LM Studio)**
  - No API key needed for local servers
  - Model: Name of your local model (e.g., ``llama3``, ``mistral``, ``codellama``)
  - URL: ``http://localhost:11434/v1`` (Ollama default) or ``http://localhost:1234/v1`` (LM Studio)

**NVIDIA**
  - API Key: Get from `build.nvidia.com <https://build.nvidia.com>`_
  - Uses NVIDIA's NIM API for hosted models

Using the AI Assistant Effectively
----------------------------------

**Ask for Script Help**

.. code-block:: text

   "Create a script that makes an entity follow the mouse cursor"
   "How do I make a player jump with physics?"
   "Fix this script: [paste your code]"

**Ask About the Engine**

.. code-block:: text

   "How does collision detection work in AxisPy?"
   "What's the difference between kinematic and dynamic rigidbodies?"
   "How do I play a sound effect from a script?"

**Let the Assistant Modify Your Project**

.. code-block:: text

   "Create an enemy entity with a sprite and a box collider"
   "Add a Rigidbody2D to the Player entity"
   "Write a script for enemy AI and attach it to the Enemy entity"

**Context-Aware Questions**

The assistant has access to your project context:

.. code-block:: text

   "What entities are in my current scene?"
   "Read my Player script and suggest improvements"
   "Why isn't my collision detection working?"

AI Tools Reference
------------------

The AI Assistant can call these tools to interact with your project:

Project Inspection
~~~~~~~~~~~~~~~~~~

- ``list_entities(limit=50)`` — List all entities and their components
- ``get_entity_info(entity_name)`` — Get detailed info about a specific entity
- ``read_script(script_path)`` — Read source code of a script (e.g., ``"scripts/player.py"``)
- ``read_scene(scene_path)`` — Read raw JSON of a scene file

Project Modification
~~~~~~~~~~~~~~~~~~~~

- ``write_script(script_path, content)`` — Create or overwrite a script file
- ``edit_script(script_path, old_text, new_text)`` — Replace text in an existing script
- ``create_entity(entity_name, components, layer="Default", groups=[])`` — Add a new entity
- ``add_component_to_entity(entity_name, component_type, properties={})`` — Attach a component
- ``modify_component(entity_name, component_type, property, value)`` — Change a property
- ``delete_entity(entity_name)`` — Remove an entity from the scene

Scripting Tips
~~~~~~~~~~~~~~

When the AI writes scripts, it follows these conventions:

- **No import statements needed** — ``Input``, ``Transform``, components, etc. are injected
- Use ``self.entity`` to access the entity the script is attached to
- Use ``self.logger.info()`` for debug output (visible in Console dock)
- Use injected helpers like ``self.find()``, ``self.tween()``, ``self.instantiate_prefab()``

Example of what the AI produces:

.. code-block:: python

  from core.input import Input
  from core.components import Transform
  class FollowMouse:
    def on_update(self, dt: float):
          
      t = self.entity.get_component(Transform)
      if t:
        mx, my = Input.get_game_mouse_position()
        t.x = mx
        t.y = my

Advanced: Session Management
------------------------------

Sessions are stored per-project in ``.ai_sessions/`` folder. Each session includes:

- Conversation history
- Timestamps
- Unique IDs for tracking

Sessions persist across editor restarts, so you can continue conversations later.

To programmatically manage sessions from a script:

.. code-block:: python

   # Access the chat manager through the editor (if needed in custom tooling)
   # This is advanced usage for editor plugin development
   from core.ai.chat_manager import ChatManager
   
   manager = ChatManager()
   manager.set_project_path("/path/to/project")
   
   # Create a new session
   session_id = manager.create_new_session("My Session")
   
   # Switch sessions
   manager.switch_session(session_id)
   
   # Clear history
   manager.clear_history()

Troubleshooting
---------------

**"No AI provider configured"**
  - Go to Project Settings → AI and set your API key

**"AI provider is not available"**
  - Check your internet connection
  - Verify your API key is valid
  - Check the provider's status page

**Local LLM not responding**
  - Ensure Ollama or LM Studio is running
  - Verify the URL (default: ``http://localhost:11434/v1`` for Ollama)
  - Check that the model name matches exactly

**Assistant can't find my entities**
  - Make sure you've saved your scene
  - The assistant reads from disk, not the live editor state

Script Editor snippets you may need
-----------------------------------

While the AI Assistant helps you write scripts, here are common patterns you might ask it to generate or use directly:

- **Log to console from a script**

.. code-block:: python

   class MyScript:
       def on_start(self):
           self.logger.info("Script started on", entity=self.entity.name)
           self.logger.debug("Debug info", value=42)

- **Get AI Assistant chat manager (for advanced use)**

.. code-block:: python

   from core.ai.chat_manager import ChatManager
   
   class AIHelper:
       def on_start(self):
           # Access the global chat manager (editor only)
           self.chat = ChatManager()
           self.chat.set_project_path(self.entity.world.project_path)

- **Programmatically send a message to AI (editor tooling)**

.. code-block:: python

   from core.ai.chat_manager import ChatManager
   
   class AIScriptHelper:
       def ask_ai(self, question: str):
           chat = ChatManager()
           response = chat.send_message(question)
           self.logger.info("AI response", text=response[:200])

- **Check if AI is available before using**

.. code-block:: python

   from core.ai.chat_manager import ChatManager
   
   class SmartHelper:
       def on_start(self):
           chat = ChatManager()
           if chat.provider and chat.provider.is_available():
               self.logger.info("AI is ready")
           else:
               self.logger.warning("AI not configured")
