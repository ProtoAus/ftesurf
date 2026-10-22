// Minimal P603 route only: unrelated opt-in suites are not compiled or claimed.
void() P603_HttpFrame = {};
float(string cmd) P603_FollowCommand = { return FALSE; };
float(string cmd) P603_HttpCommand = { return FALSE; };
float(string cmd) P603_LifeCommand = { return FALSE; };
float(string cmd) P603_FontCommand = { return FALSE; };
float(string cmd) P603_DenseCommand = { return FALSE; };
