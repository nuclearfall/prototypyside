import json
import random
import math
from enum import Enum, auto
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional

# ------------------------------------------------------------
# ENUMS & CONSTANTS
# ------------------------------------------------------------

class AtomCategory(Enum):
    CONTROL   = auto()
    PREDICATE = auto()
    CONNECTOR = auto()
    ACTION    = auto()
    MODIFIER  = auto()
    LITERAL   = auto()

# Colour map → hex + friendly name
CATEGORY_COLOUR: Dict[AtomCategory, Tuple[str, str]] = {
    AtomCategory.CONTROL:   ("#d4af37", "gold"),
    AtomCategory.PREDICATE: ("#3b82f6", "blue"),
    AtomCategory.CONNECTOR: ("#6b7280", "grey"),
    AtomCategory.ACTION:    ("#22c55e", "green"),
    AtomCategory.MODIFIER:  ("#8b5cf6", "violet"),
    AtomCategory.LITERAL:   ("#ffffff", "white"),
}

# Adjacency – **required** successor classes for each category
REQUIRED_NEXT: Dict[AtomCategory, Set[AtomCategory]] = {
    AtomCategory.CONTROL:   {AtomCategory.PREDICATE},
    AtomCategory.PREDICATE: {AtomCategory.ACTION, AtomCategory.CONNECTOR, AtomCategory.MODIFIER},
    AtomCategory.CONNECTOR: {AtomCategory.PREDICATE, AtomCategory.ACTION, AtomCategory.MODIFIER},
    AtomCategory.ACTION:    {AtomCategory.CONNECTOR, AtomCategory.MODIFIER},
    AtomCategory.MODIFIER:  {AtomCategory.CONNECTOR, AtomCategory.MODIFIER, AtomCategory.ACTION},
    AtomCategory.LITERAL:   {AtomCategory.CONNECTOR, AtomCategory.MODIFIER},
}

# A rule **must** start with CONTROL; it may end on ACTION or MODIFIER
CAN_BEGIN: Set[AtomCategory] = {AtomCategory.CONTROL}
CAN_END:   Set[AtomCategory] = {AtomCategory.ACTION, AtomCategory.MODIFIER}

# ------------------------------------------------------------
# DATA CLASSES
# ------------------------------------------------------------

@dataclass(frozen=True)
class Atomic:
    """Represents one *half* of a card, plus rich grammar metadata."""

    text: str
    category: AtomCategory
    reward: int = 1

    # derived fields
    colour_hex: str = field(init=False)
    colour_name: str = field(init=False)
    can_begin: bool = field(init=False)
    can_end: bool = field(init=False)
    required_prev: Set[str] = field(init=False)
    optional_prev: Set[str] = field(init=False)
    required_next: Set[str] = field(init=False)
    optional_next: Set[str] = field(init=False)

    def __post_init__(self):
        hex_code, name = CATEGORY_COLOUR[self.category]
        object.__setattr__(self, "colour_hex", hex_code)
        object.__setattr__(self, "colour_name", name)
        object.__setattr__(self, "can_begin", self.category in CAN_BEGIN)
        object.__setattr__(self, "can_end",   self.category in CAN_END)

        required_prev: Set[str] = set()  # none in this grammar version
        optional_prev = {c.name for c in REQUIRED_NEXT if self.category in REQUIRED_NEXT[c]}
        required_next = {c.name for c in REQUIRED_NEXT[self.category]}
        optional_next = {c.name for c in AtomCategory} - required_next

        object.__setattr__(self, "required_prev", required_prev)
        object.__setattr__(self, "optional_prev", optional_prev)
        object.__setattr__(self, "required_next", required_next)
        object.__setattr__(self, "optional_next", optional_next)

    def to_json_dict(self) -> Dict:
        """Return a JSON‑serialisable dict (converts enums & sets)."""
        d = asdict(self)
        d["category"] = self.category.name
        # convert sets to sorted lists for stable output
        for k in ("required_prev", "optional_prev", "required_next", "optional_next"):
            d[k] = sorted(list(d[k]))
        return d


@dataclass
class Card:
    id: str
    top: Atomic
    bottom: Atomic

    def __post_init__(self):
        if self.top.category == self.bottom.category:
            raise ValueError("Card halves must differ in category")

    def to_json_dict(self) -> Dict[str, Dict]:
        return {
            "top": self.top.to_json_dict(),
            "bottom": self.bottom.to_json_dict(),
        }


# ------------------------------------------------------------
# GENERATORS
# ------------------------------------------------------------

class PredicateGenerator:
    """Generates predicate atoms by combining subjects and conditions."""

    def __init__(self, predicates: List[Tuple[str, AtomCategory, int]]):
        """
        Initializes the generator with a list of generated predicates.
        
        Args:
            predicates: A list of atoms in the format (text, category, reward).
        """
        self.predicates = predicates

    @classmethod
    def from_components(
        cls,
        subjects: List[str],
        conditions: List[str],
        count: int = -1,
    ) -> "PredicateGenerator":
        """
        Creates a set of predicates by combining subjects and conditions.

        Args:
            subjects: A list of predicate beginnings (e.g., "The Acting Player has").
            conditions: A list of predicate endings (e.g., "more than 20 victory points").
            count: The number of unique predicates to generate. If -1, all possible
                   combinations are generated.

        Returns:
            A PredicateGenerator instance containing the generated predicates.
        """
        all_combinations = [
            (f"{s} {c}".strip(), AtomCategory.PREDICATE, 1)
            for s in subjects
            for c in conditions
        ]

        if count == -1 or count >= len(all_combinations):
            generated_predicates = all_combinations
        else:
            if count > len(all_combinations):
                print(f"Warning: Requested {count} predicates, but only "
                      f"{len(all_combinations)} unique combinations are possible. "
                      "Returning all combinations.")
            generated_predicates = random.sample(all_combinations, min(count, len(all_combinations)))

        return cls(generated_predicates)

    def to_list(self) -> List[Tuple[str, AtomCategory, int]]:
        """Returns the generated predicates as a list."""
        return self.predicates


class AtomicGenerator:
    def __init__(self):
        self.pool: Dict[AtomCategory, List[Atomic]] = {c: [] for c in AtomCategory}

    def add(self, text: str, category: AtomCategory, reward: int = 1):
        self.pool[category].append(Atomic(text=text, category=category, reward=reward))

    def extend(self, atoms: List[Tuple[str, AtomCategory, int]]):
        for text, cat, rew in atoms:
            self.add(text, cat, rew)

    def random(self, cat: AtomCategory) -> Atomic:
        return random.choice(self.pool[cat])

    def random_different_from(self, cat: AtomCategory) -> Atomic:
        other_cats = [c for c in AtomCategory if c != cat and self.pool[c]]
        if not other_cats:
            raise ValueError(f"Cannot find a different category from {cat.name} with atoms in it.")
        return self.random(random.choice(other_cats))


class CardGenerator:
    def __init__(self, atom_factory: AtomicGenerator):
        self.f = atom_factory
        self._idx = 1
        self.weights = self._calculate_balanced_weights()
        
        print("Card Generator initialised with the following balanced category weights:")
        for cat, weight in zip(list(AtomCategory), self.weights):
            if weight > 0:
                print(f"  - {cat.name:<10}: {weight:.2f}")

    def _calculate_balanced_weights(self) -> List[float]:
        """
        Calculates category selection weights, balancing them based on the number
        of atoms available in each category's pool. This ensures that categories
        with very small pools get a fair chance to appear and that categories
        with very large pools do not dominate the card generation.
        """
        base_weights = {
            AtomCategory.CONTROL:   15,
            AtomCategory.PREDICATE: 20,
            AtomCategory.CONNECTOR: 15,
            AtomCategory.ACTION:    20,
            AtomCategory.MODIFIER:  15,
            AtomCategory.LITERAL:   15,
        }
        
        pool_sizes = {c: len(self.f.pool[c]) for c in AtomCategory}
        non_empty_pools = {c: s for c, s in pool_sizes.items() if s > 0}

        if not non_empty_pools:
            return [0.0] * len(AtomCategory)

        avg_size = sum(non_empty_pools.values()) / len(non_empty_pools)
        
        final_weights = []
        for cat in list(AtomCategory):
            if cat not in non_empty_pools:
                final_weights.append(0.0)
                continue

            size = pool_sizes[cat]
            base_weight = base_weights[cat]
            
            # Create an adjustment factor. For larger-than-average pools, this will
            # be < 1, and for smaller-than-average pools, it will be > 1.
            # We use math.sqrt to soften the effect and prevent extreme weight shifts.
            adjustment_factor = math.sqrt(avg_size / size)
            
            final_weights.append(base_weight * adjustment_factor)
            
        return final_weights

    def _pick_top_cat(self) -> AtomCategory:
        """Picks a category for the top half of a card using the balanced weights."""
        if not any(self.weights):
            raise ValueError("All atom pools are empty, cannot generate cards.")
            
        return random.choices(
            population=list(AtomCategory),
            weights=self.weights,
            k=1
        )[0]

    def generate_card(self) -> Card:
        top_cat = self._pick_top_cat()
        top_atom = self.f.random(top_cat)
        bottom_atom = self.f.random_different_from(top_cat)
        card = Card(id=f"C{self._idx:03d}", top=top_atom, bottom=bottom_atom)
        self._idx += 1
        return card

    def generate_deck(self, n: int) -> List[Card]:
        return [self.generate_card() for _ in range(n)]



@dataclass
class Card:
    id: str
    top: Atomic
    bottom: Atomic

    def __post_init__(self):
        if self.top.category == self.bottom.category:
            raise ValueError("Card halves must have different categories")

    def to_json(self) -> Dict:
        return {"top": self.top.to_json(), "bottom": self.bottom.to_json()}
# ------------------------------------------------------------
# SERIALISATION HELPERS
# ------------------------------------------------------------

DICT_PATH = Path("dictionary.json")

def load_dictionary() -> Dict[str, Dict]:
    if DICT_PATH.exists():
        return json.loads(DICT_PATH.read_text())
    return {}

def save_dictionary(d: Dict[str, Dict]):
    DICT_PATH.write_text(json.dumps(d, indent=2))


def append_cards_to_dict(cards: List[Card]):
    data = load_dictionary()
    for c in cards:
        data[c.id] = c.to_json_dict()
    save_dictionary(data)


# ------------------------------------------------------------
# DEMO
# ------------------------------------------------------------

def _bootstrap() -> AtomicGenerator:
    """Initializes an AtomicGenerator with a sample and generated atom set."""
    g = AtomicGenerator()
    
    # Add a small, core set of atoms
    g.extend([
        ("IF", AtomCategory.CONTROL, 0),
        ("WHEN", AtomCategory.CONTROL, 0),
        ("THEN", AtomCategory.CONNECTOR, 0),
        ("AND", AtomCategory.CONNECTOR, 0),
        ("gain 2 blue cubes", AtomCategory.ACTION, 2),
        ("draw 1 card", AtomCategory.ACTION, 1),
        ("gain 2 vp for each star they have in the System", AtomCategory.ACTION, 1),
        ("FOR EACH red cube", AtomCategory.MODIFIER, 0),
        ("ONCE PER TURN", AtomCategory.MODIFIER, 0),
        ("1", AtomCategory.LITERAL, 0),
        ("2", AtomCategory.LITERAL, 0),
    ])

    # Use the new PredicateGenerator to create a large, imbalanced pool
    print("Generating a large number of predicates...")
    pred_subjects = [
        "The Acting Player has", "Each Player has", "Next Player has",
        "Any players have", "The System Memory contains"
    ]
    pred_conditions = [
        "less than 10 cards in hand", "an even number of total resources",
        "the maximum number of cursor tokens", "more than 20 victory points",
        "at least 1 blue cube", "no red cubes", "exactly 5 credits"
    ]
    
    # Generate 30 predicates from the possible 35 combinations
    predicate_generator = PredicateGenerator.from_components(
        subjects=pred_subjects,
        conditions=pred_conditions,
        count=30
    )
    
    # Add the generated predicates to the main generator
    g.extend(predicate_generator.to_list())
    print(f"Added {len(predicate_generator.to_list())} predicates to the atom pool.\n")

    return g


if __name__ == "__main__":
    random.seed(42)
    factory = _bootstrap()
    
    # The CardGenerator will now automatically balance the weights
    card_gen = CardGenerator(factory)
    
    deck = card_gen.generate_deck(20)
    
    # To save the generated deck to dictionary.json, uncomment the next line
    # append_cards_to_dict(deck)

    print("\n--- Generated Deck ---")
    for card in deck:
        print(f"{card.id}\n  TOP: [{card.top.category.name}] {card.top.text}\n  BOT: [{card.bottom.category.name}] {card.bottom.text}\n")