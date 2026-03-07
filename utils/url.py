from urllib.parse import urlencode


def build_query(params_dict):
	if not params_dict:
		return ""
	cleaned = {}
	for key, value in params_dict.items():
		if value is None or value == "" or value == []:
			continue
		if isinstance(value, (list, tuple, set)):
			values = [item for item in value if item is not None and item != ""]
			if not values:
				continue
			cleaned[key] = values
		else:
			cleaned[key] = value
	return urlencode(cleaned, doseq=True)
