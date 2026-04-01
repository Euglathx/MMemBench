from pathlib import Path

path = Path(r"E:/Code/M3Bench/M3Bench_new/src/simulator/strategic_simulator.py")
text = path.read_text(encoding="utf-8")
orig = text

replacements = [
    (
        "        # Task 1D: Store conversation history for batch integration\n        self.conversation_history: List[Dict[str, Any]] = []\n",
        "        # Task 1D: Store conversation history for batch integration\n        self.conversation_history: List[Dict[str, Any]] = []\n\n        # Window B: Turn-level image exposure contract state\n        self._resolved_task_images: List[str] = []\n        self._image_exposure_store: Dict[str, Dict[str, Any]] = {}\n",
    ),
    (
        "        self.turn_count = 0\n        self.evaluator.reset_for_task()\n\n        # Initialize memory\n",
        "        self.turn_count = 0\n        self.evaluator.reset_for_task(\n            task_type=task_type,\n            num_images=len(self.task_state.images)\n        )\n        self.image_policy.reset()\n        self._resolved_task_images = []\n        self._image_exposure_store = {}\n\n        # Initialize memory\n",
    ),
    (
        "        # 3. Determine images to send\n        images_to_send = self._get_images_for_turn(action)\n",
        "        # 3. Determine images to send\n        images_to_send = self._get_images_for_turn(action)\n        turn_protocol = self._build_turn_evaluation_context(\n            images_to_send=images_to_send,\n            turn_ground_truth=turn_ground_truth,\n            action=action\n        )\n",
    ),
    (
        "                \"task_expected_answer\": self.task_state.expected_answer,  # Keep task-level for reference\n                # === Phase 2 Task 2.5: Pass images_sent to evaluator ===\n                \"images_sent\": images_to_send,\n                \"total_task_images\": len(self.task_state.images) if self.task_state.images else 0\n            }\n        )\n",
        "                \"task_expected_answer\": self.task_state.expected_answer,  # Keep task-level for reference\n                # === Phase 2 Task 2.5: Pass images_sent to evaluator ===\n                \"images_sent\": images_to_send,\n                \"total_task_images\": len(self.task_state.images) if self.task_state.images else 0,\n                **turn_protocol\n            }\n        )\n",
    ),
    (
        "            \"evaluation\": eval_result.to_dict(),\n            \"images_sent\": images_to_send\n        })\n",
        "            \"evaluation\": eval_result.to_dict(),\n            \"images_sent\": images_to_send,\n            \"turn_input_mode\": turn_protocol[\"turn_input_mode\"],\n            \"visible_image_refs\": turn_protocol[\"visible_image_refs\"],\n            \"memory_image_refs\": turn_protocol[\"memory_image_refs\"],\n            \"new_images_sent_count\": turn_protocol[\"new_images_sent_count\"]\n        })\n",
    ),
    (
        "            'evaluation': eval_result.to_dict(),\n            'timestamp': datetime.now().isoformat(),\n            'phase': phase.phase_name,\n            'difficulty': self.task_state.difficulty_level\n        })\n",
        "            'evaluation': eval_result.to_dict(),\n            'timestamp': datetime.now().isoformat(),\n            'phase': phase.phase_name,\n            'difficulty': self.task_state.difficulty_level,\n            'turn_input_mode': turn_protocol[\"turn_input_mode\"],\n            'visible_image_refs': turn_protocol[\"visible_image_refs\"],\n            'memory_image_refs': turn_protocol[\"memory_image_refs\"],\n            'new_images_sent_count': turn_protocol[\"new_images_sent_count\"]\n        })\n",
    ),
    (
        "        return {\n            \"turn\": self.turn_count,\n            \"action\": action,\n            \"message\": message,\n            \"response\": model_content,\n            \"evaluation\": eval_result.to_dict(),\n            \"should_continue\": should_continue,\n            \"phase\": phase.phase_name,\n            \"difficulty\": self.task_state.difficulty_level\n        }\n",
        "        return {\n            \"turn\": self.turn_count,\n            \"action\": action,\n            \"message\": message,\n            \"response\": model_content,\n            \"evaluation\": eval_result.to_dict(),\n            \"images_sent\": images_to_send if images_to_send else [],\n            \"turn_input_mode\": turn_protocol[\"turn_input_mode\"],\n            \"visible_image_refs\": turn_protocol[\"visible_image_refs\"],\n            \"memory_image_refs\": turn_protocol[\"memory_image_refs\"],\n            \"new_images_sent_count\": turn_protocol[\"new_images_sent_count\"],\n            \"should_continue\": should_continue,\n            \"phase\": phase.phase_name,\n            \"difficulty\": self.task_state.difficulty_level\n        }\n",
    ),
    (
        "        # === Phase 2 Task 2.5: Use ImagePolicyManager to decide which images to send ===\n        images_to_send = self.image_policy.get_images_to_send(\n",
        "        self._resolved_task_images = all_resolved_images\n\n        # === Phase 2 Task 2.5: Use ImagePolicyManager to decide which images to send ===\n        images_to_send = self.image_policy.get_images_to_send(\n",
    ),
]

for old, new in replacements:
    if old not in text:
        raise SystemExit(f"Missing target snippet:\n{old}")
    text = text.replace(old, new, 1)

insert_after = "    def _call_core_model_for_action(self) -> Tuple[str, str, Dict[str, Any]]:\n"
helper_block = '''    def _image_ref_sort_key(self, image_ref: str) -> int:
        match = re.search(r"(\\d+)$", image_ref)
        return int(match.group(1)) if match else 10**9

    def _get_image_ref_for_resolved_path(self, image_path: str) -> str:
        try:
            idx = self._resolved_task_images.index(image_path)
        except ValueError:
            return image_path
        return f"Image {self._global_image_offset + idx}"

    def _infer_expected_source(
        self,
        turn_ground_truth: Optional[TurnGroundTruth],
        visible_image_refs: List[str],
        memory_image_refs: List[str]
    ) -> str:
        hints = turn_ground_truth.evaluation_hints if turn_ground_truth else {}
        if hints.get("fresh_visual_required"):
            return "fresh_visual"
        if hints.get("memory_only"):
            return "memory"
        if visible_image_refs and memory_image_refs:
            return "either"
        if visible_image_refs:
            return "fresh_visual"
        if memory_image_refs:
            return "memory"
        return "either"

    def _update_image_exposure_store(self, visible_paths: List[str]):
        for image_path in visible_paths:
            image_ref = self._get_image_ref_for_resolved_path(image_path)
            existing = self._image_exposure_store.get(image_ref)
            if existing is None:
                self._image_exposure_store[image_ref] = {
                    "path": image_path,
                    "first_exposed_turn": self.turn_count,
                    "last_visible_turn": self.turn_count,
                }
            else:
                existing["last_visible_turn"] = self.turn_count
                existing["path"] = image_path

    def _build_turn_evaluation_context(
        self,
        images_to_send: List[str],
        turn_ground_truth: Optional[TurnGroundTruth],
        action: str
    ) -> Dict[str, Any]:
        visible_paths = list(images_to_send or [])
        visible_image_refs = [self._get_image_ref_for_resolved_path(path) for path in visible_paths]
        memory_image_refs = sorted(
            self._image_exposure_store.keys(),
            key=self._image_ref_sort_key,
        )

        if visible_image_refs and memory_image_refs:
            turn_input_mode = "mixed"
        elif visible_image_refs:
            turn_input_mode = "fresh_visual"
        elif memory_image_refs:
            turn_input_mode = "memory_only"
        else:
            turn_input_mode = "no_visual"

        expected_source = self._infer_expected_source(
            turn_ground_truth,
            visible_image_refs,
            memory_image_refs,
        )
        hints = turn_ground_truth.evaluation_hints if turn_ground_truth else {}
        target_variables = list(hints.get("target_variables", []))
        if turn_ground_truth and turn_ground_truth.required_images:
            target_variables.extend(
                [f"image_ref:{self._global_image_offset + idx}" for idx in turn_ground_truth.required_images]
            )

        evaluator_memory_image_paths = []
        for image_ref in memory_image_refs:
            image_path = self._image_exposure_store.get(image_ref, {}).get("path")
            if image_path and image_path not in evaluator_memory_image_paths:
                evaluator_memory_image_paths.append(image_path)

        turn_context = {
            "turn_input_mode": turn_input_mode,
            "visible_image_refs": visible_image_refs,
            "memory_image_refs": memory_image_refs,
            "new_images_sent_count": len(visible_image_refs),
            "image_policy": self.image_policy.policy.value,
            "fresh_visual_required": expected_source == "fresh_visual",
            "current_question_scope": {
                "expected_source": expected_source,
                "target_variables": target_variables,
            },
            "target_variables": target_variables,
            "evaluator_visible_image_paths": visible_paths,
            "evaluator_memory_image_paths": evaluator_memory_image_paths,
        }

        self._update_image_exposure_store(visible_paths)
        return turn_context

'''
if helper_block not in text:
    if insert_after not in text:
        raise SystemExit("Missing helper insertion point")
    text = text.replace(insert_after, helper_block + insert_after, 1)

if text == orig:
    raise SystemExit("No changes applied")

path.write_text(text, encoding="utf-8")
print("patched strategic_simulator.py")