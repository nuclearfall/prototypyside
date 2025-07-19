from prototypyside.utils.proto_helpers import issue_pid

class MailRoom:
    def __init__(self, registry):
        self.pid = issue_pid("mail")
        self._registry = registry
        self._object_registry = getattr(registry, "object_registry", None)
        self._targets = {}
        # Connect registry signals
        registry.object_registered.connect(self.add_target)
        registry.object_deregistered.connect(self.remove_target)

    def has_sender(self, packet):
        return packet.get("sender") in self._targets

    def has_target(self, packet):
        return packet.get("target") in self._targets

    def add_target(self, pid):
        # Prefer main registry, then object registry if present
        target = self._registry.get(pid)
        if not target and self._object_registry:
            target = self._object_registry.get(pid)
        if target:
            self._targets[pid] = target

    def remove_target(self, pid):
        self._targets.pop(pid, None)

    def send_packet(self, packet):
        sender_pid = packet.get("sender")
        target_pid = packet.get("target")

        # suspects = []
        # if sender_pid and sender_pid not in self._targets:
        #     if not self.req_register(sender_pid):
        #         suspects.append(sender_pid)
        # if target_pid and target_pid not in self._targets:
        #     if not self.req_register(target_pid):
        #         suspects.append(target_pid)
        # if suspects:
        #     raise ValueError(f"These PIDs are not in the registry or mail room and could not be registered: {suspects}")

        # All good, deliver!

        if target_pid in self._targets and sender_pid:
            self._targets[target_pid].receive_packet(packet)
        else:
            raise ValueError(f"Target {target_pid} not found in mail room.")

    # def req_register(self, obj):
    #     """Attempt to register the object by pid in the proper registry."""
    #     # Try both registries
    #     obj = self._registry.get(pid)
    #     if obj:
    #         self.add_target(pid)
    #         return True
    #     elif self._object_registry:
    #         obj = self._object_registry.get(pid)
    #         if obj:
    #             self.add_target(pid)
    #             return True
    #     return False
