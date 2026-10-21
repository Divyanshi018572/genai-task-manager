# Assignment spec and traceability

Source: `GenAI_Intern_Hiring_Round1_Assignment.docx.pdf` and the extracted text in `assignment_content.txt`.

| Requirement | Implementation | Evidence |
|---|---|---|
| Create a task with title and due date | `tool_add_task`, `add_task` | notebook demo and pytest |
| View pending tasks | `tool_list_tasks` | notebook demo and pytest |
| Mark a task completed | `tool_complete_task` | notebook demo and pytest |
| Get details including due date and status | `tool_get_task_details` | notebook demo and pytest |
| Ask for clarification on ambiguous requests | `tool_complete_task` returns `ambiguous`; `Agent._reply_from_results` lists candidates | `test_agent_ambiguous`, eval case `ambiguous_complete` |
| Friendly not-found reply | `tool_complete_task`, `tool_get_task_details` | not-found test |
| Six notebook sections in order | `notebook_source.py` Markdown | generated notebook |

Update the Evidence column only after you run the command and see the result.
