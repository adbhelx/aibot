import json
import config

class ContentManager:
    def __init__(self):
        self.content = self.load_content()

    def load_content(self):
        try:
            with open(config.CONTENT_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                "lessons": {},
                "quizzes": {},
                "phrases": {},
                "vocabulary": {},
                "grammar_rules": {},
                "dialogues": {}
            }

    def save_content(self):
        with open(config.CONTENT_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.content, f, ensure_ascii=False, indent=2)

    def add_lesson(self, lesson_id, title, description, content_text, quiz_id=None):
        self.content["lessons"][lesson_id] = {
            "title": title,
            "description": description,
            "content": content_text,
            "quiz_id": quiz_id
        }
        self.save_content()

    def get_lesson(self, lesson_id):
        return self.content["lessons"].get(lesson_id)

    def add_quiz(self, quiz_id, title, questions):
        self.content["quizzes"][quiz_id] = {
            "title": title,
            "questions": questions  # List of {'question': '...', 'options': [...], 'answer': '...'} 
        }
        self.save_content()

    def get_quiz(self, quiz_id):
        return self.content["quizzes"].get(quiz_id)

    def get_random_phrase(self):
        import random
        phrases = list(self.content["phrases"].values())
        if phrases:
            return random.choice(phrases)
        return None

    def add_phrase(self, phrase_id, text, translation):
        self.content["phrases"][phrase_id] = {"text": text, "translation": translation}
        self.save_content()

    def get_all_lessons(self):
        return self.content["lessons"]

    def get_all_quizzes(self):
        return self.content["quizzes"]

    def get_all_phrases(self):
        return self.content["phrases"]

    def get_all_vocabulary(self):
        return self.content["vocabulary"]

    def add_vocabulary(self, word, pinyin, translation):
        self.content["vocabulary"][word] = {"pinyin": pinyin, "translation": translation}
        self.save_content()

    def get_vocabulary_item(self, word):
        return self.content["vocabulary"].get(word)

    def add_grammar_rule(self, rule_id, title, explanation, examples):
        self.content["grammar_rules"][rule_id] = {
            "title": title,
            "explanation": explanation,
            "examples": examples
        }
        self.save_content()

    def get_grammar_rule(self, rule_id):
        return self.content["grammar_rules"].get(rule_id)

    def add_dialogue(self, dialogue_id, title, script):
        self.content["dialogues"][dialogue_id] = {
            "title": title,
            "script": script # List of {'speaker': '...', 'text': '...'}
        }
        self.save_content()

    def get_dialogue(self, dialogue_id):
        return self.content["dialogues"].get(dialogue_id)

    def search_content(self, keyword, content_type=None):
        results = []
        search_types = [content_type] if content_type else self.content.keys()

        for c_type in search_types:
            if c_type in self.content:
                for item_id, item_data in self.content[c_type].items():
                    if keyword.lower() in json.dumps(item_data, ensure_ascii=False).lower():
                        results.append({"type": c_type, "id": item_id, "data": item_data})
        return results


    def add_file_data(self, file_id, file_type, file_name=None, user_id=None):
        if "files" not in self.content:
            self.content["files"] = {}
        
        file_key = f"{file_type}_{file_id}"
        
        self.content["files"][file_key] = {
            "file_id": file_id,
            "file_type": file_type,
            "file_name": file_name,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        }
        self.save_content()

    def get_file_data(self, file_key):
        return self.content.get("files", {}).get(file_key)

